"""CLI health reporting and argument validation.

The CLI sits in a shipping-release gate, so its exit codes are the product.
These tests pin the conditions under which `status` reports unhealthy and
`explain`/`screen` refuse rather than traceback.
"""

import contextlib
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from xscreen.cli import main
from xscreen.fetch import load_manifest, refresh, verify_corpus

FIX = Path(__file__).parent / "fixtures"
FULL = ("CSL", "SDN", "SDN_ALT", "SDN_ADD", "NONSDN", "DPL")


class CliCase(unittest.TestCase):
    def setUp(self):
        self.home = Path(tempfile.mkdtemp())
        self.data = self.home / "lists"
        self.data.mkdir()
        for f in FIX.glob("*.raw"):
            shutil.copy(f, self.data / f.name)
        refresh(self.data, FULL, offline=True)

    def tearDown(self):
        shutil.rmtree(self.home, ignore_errors=True)

    def _run(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(["--home", str(self.home), *argv])
        return code, out.getvalue(), err.getvalue()


class TestStatusReportsCorpusIntegrity(CliCase):
    def test_healthy_snapshot_is_verified(self):
        code, out, _ = self._run("status", "--backend", "offline")
        self.assertIn("corpus:         VERIFIED", out)
        self.assertIn("coverage:       OK", out)
        self.assertEqual(code, 0)

    def test_tampered_corpus_is_unhealthy(self):
        p = self.data / "parties.jsonl"
        p.write_text("\n".join(l for l in p.read_text().splitlines()
                               if '"SDN:1001"' not in l))
        code, out, _ = self._run("status", "--backend", "offline")
        self.assertIn("corpus:         MISMATCH", out)
        self.assertEqual(code, 1)

    def test_verify_corpus_helper_agrees_with_status(self):
        ok, msg = verify_corpus(self.data, load_manifest(self.data))
        self.assertTrue(ok, msg)


class TestExplainRefusesCleanly(CliCase):
    def test_tampered_corpus_is_a_message_not_a_traceback(self):
        p = self.data / "parties.jsonl"
        p.write_text(p.read_text() + '\n{"uid":"SDN:999","source":"SDN","native_id":"999","name":"X"}')
        code, _, err = self._run("explain", "Northwind Heavy Machinery")
        self.assertEqual(code, 1)
        self.assertIn("does not match the digest", err)

    def test_stale_snapshot_is_disclosed(self):
        mp = self.data / "manifest.json"
        man = json.loads(mp.read_text())
        for f in man["files"]:
            if f.get("fetched_at"):
                f["fetched_at"] = "2023-01-01T00:00:00+00:00"
        mp.write_text(json.dumps(man))
        code, out, err = self._run("explain", "Northwind Heavy Machinery")
        self.assertEqual(code, 0)
        self.assertIn("days old", err)
        self.assertIn("EXACT", out)


class TestScreenArgumentValidation(CliCase):
    def test_bad_as_of_is_a_usage_error(self):
        party = self.home / "p.csv"
        party.write_text("name\nSunny Day Bakery\n")
        code, _, err = self._run("screen", str(party), "--no-llm", "--as-of", "2026-13-45",
                                 "--out", str(self.home / "run"))
        self.assertEqual(code, 1)
        self.assertIn("--as-of", err)

    def test_refresh_audit_entry_carries_the_corpus_digest(self):
        from xscreen.audit import AuditLog
        code, _, _ = self._run("refresh", "--offline", "--sources", *FULL)
        self.assertEqual(code, 0)
        entries = [e for e in AuditLog(self.home / "audit" / "screening-audit.jsonl").entries()
                   if e["event"] == "lists.refresh"]
        self.assertEqual(len(entries[-1]["payload"]["corpus_sha256"]), 64)


if __name__ == "__main__":
    unittest.main()
