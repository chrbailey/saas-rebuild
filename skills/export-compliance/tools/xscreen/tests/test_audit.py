import json
import tempfile
import unittest
from pathlib import Path

from xscreen.audit import AuditLog


class TestAuditChain(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = Path(self.dir.name) / "audit.jsonl"
        self.log = AuditLog(self.path)

    def tearDown(self):
        self.dir.cleanup()

    def _seed(self, n: int = 4):
        for i in range(n):
            self.log.append("case.screened", {"ref": f"C-{i}", "disposition": "CLEAR"},
                            actor="tester")

    def test_empty_log_is_not_silently_valid(self):
        intact, problems = self.log.verify()
        self.assertFalse(intact)
        self.assertIn("audit log is empty", problems)

    def test_chain_intact_after_appends(self):
        self._seed()
        intact, problems = self.log.verify()
        self.assertTrue(intact, problems)
        seq, head = self.log.head()
        self.assertEqual(seq, 4)
        self.assertEqual(len(head), 64)

    def test_sequence_is_contiguous(self):
        self._seed(3)
        seqs = [e["seq"] for e in self.log.entries()]
        self.assertEqual(seqs, [1, 2, 3])

    def test_modified_payload_is_detected(self):
        self._seed()
        lines = self.path.read_text().splitlines()
        e = json.loads(lines[1])
        e["payload"]["disposition"] = "BLOCKED"   # someone edits history
        lines[1] = json.dumps(e, ensure_ascii=False, sort_keys=True)
        self.path.write_text("\n".join(lines) + "\n")

        intact, problems = self.log.verify()
        self.assertFalse(intact)
        self.assertTrue(any("content hash mismatch" in p for p in problems))

    def test_recomputed_hash_still_breaks_the_chain(self):
        """A tamperer who fixes the entry's own hash still breaks prev_hash."""
        from xscreen.audit import _hash_entry
        self._seed()
        lines = self.path.read_text().splitlines()
        e = json.loads(lines[1])
        e["payload"]["disposition"] = "BLOCKED"
        e["hash"] = _hash_entry(e)
        lines[1] = json.dumps(e, ensure_ascii=False, sort_keys=True)
        self.path.write_text("\n".join(lines) + "\n")

        intact, problems = self.log.verify()
        self.assertFalse(intact)
        self.assertTrue(any("prev_hash does not match" in p for p in problems))

    def test_deleted_entry_is_detected(self):
        self._seed()
        lines = self.path.read_text().splitlines()
        del lines[1]
        self.path.write_text("\n".join(lines) + "\n")
        intact, problems = self.log.verify()
        self.assertFalse(intact)
        self.assertTrue(any("sequence is" in p for p in problems))

    def test_reordered_entries_are_detected(self):
        self._seed()
        lines = self.path.read_text().splitlines()
        lines[1], lines[2] = lines[2], lines[1]
        self.path.write_text("\n".join(lines) + "\n")
        intact, _ = self.log.verify()
        self.assertFalse(intact)

    def test_append_only_never_rewrites_existing_bytes(self):
        self._seed(2)
        before = self.path.read_bytes()
        self.log.append("run.end", {"x": 1})
        after = self.path.read_bytes()
        self.assertTrue(after.startswith(before))

    def test_actor_recorded(self):
        self.log.append("run.start", {}, actor="alice@example.com")
        self.assertEqual(next(iter(self.log.entries()))["actor"], "alice@example.com")

    def test_retention_floor_is_five_years(self):
        from datetime import datetime, timezone
        floor = self.log.retention_floor(datetime(2030, 6, 1, tzinfo=timezone.utc))
        self.assertEqual(floor, "2025-06-01")

    def test_unicode_payloads_survive_round_trip(self):
        self.log.append("case.screened", {"name": "Société Générale — Müller & Søhne"})
        intact, problems = self.log.verify()
        self.assertTrue(intact, problems)
        self.assertIn("Société", next(iter(self.log.entries()))["payload"]["name"])


if __name__ == "__main__":
    unittest.main()
