"""Cross-run comparison and operator-facing input handling.

The re-screening diff is the mechanism behind two claims the skill makes: that
a party cleared in March gets caught when designated in April, and that a
parallel run against an incumbent tool is the migration acceptance test.
Neither claim is worth anything if the diff misclassifies a new hit.
"""

import csv
import io
import tempfile
import unittest
from pathlib import Path

from xscreen.cli import read_party_file
from xscreen.report import (
    ADDED,
    CHANGED,
    NEW_HIT,
    REMOVED,
    RESOLVED,
    UNCHANGED,
    diff_dispositions,
    diff_report,
    load_dispositions,
    open_cases_report,
)

FIELDS = ["ref", "name", "disposition", "requires_human", "top_band", "top_list",
          "top_matched_name", "top_score", "rule_flags", "prohibitive_flags",
          "adjudication", "critic_findings", "screened_at", "list_manifest_digest"]


def make_csv(rows: list[dict[str, str]]) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=FIELDS, lineterminator="\n")
    w.writeheader()
    for r in rows:
        w.writerow({f: r.get(f, "") for f in FIELDS})
    return buf.getvalue()


def row(ref: str, disposition: str, name: str = "", **kw) -> dict[str, str]:
    return {"ref": ref, "name": name or f"Party {ref}", "disposition": disposition, **kw}


class TestDiff(unittest.TestCase):
    def test_newly_designated_party_is_a_new_hit(self):
        before = load_dispositions(make_csv([row("C-1", "CLEAR")]))
        after = load_dispositions(make_csv([row("C-1", "CONFIRMED_HIT", top_list="SDN")]))
        g = diff_dispositions(before, after)
        self.assertEqual(len(g[NEW_HIT]), 1)
        self.assertEqual(g[NEW_HIT][0]["ref"], "C-1")
        self.assertEqual(g[NEW_HIT][0]["before"], "CLEAR")

    def test_delisted_party_is_resolved_not_new(self):
        before = load_dispositions(make_csv([row("C-1", "CONFIRMED_HIT")]))
        after = load_dispositions(make_csv([row("C-1", "CLEAR")]))
        g = diff_dispositions(before, after)
        self.assertEqual(len(g[RESOLVED]), 1)
        self.assertEqual(len(g[NEW_HIT]), 0)

    def test_escalation_between_non_clear_states_is_changed(self):
        before = load_dispositions(make_csv([row("C-1", "REVIEW")]))
        after = load_dispositions(make_csv([row("C-1", "BLOCKED")]))
        g = diff_dispositions(before, after)
        self.assertEqual(len(g[CHANGED]), 1)
        self.assertEqual(len(g[NEW_HIT]), 0)

    def test_a_brand_new_party_that_hits_counts_as_a_new_hit(self):
        # Not "added and unremarkable" -- a party appearing for the first time
        # already hitting is exactly as urgent as one that newly started to.
        before = load_dispositions(make_csv([]))
        after = load_dispositions(make_csv([row("C-9", "CONFIRMED_HIT")]))
        g = diff_dispositions(before, after)
        self.assertEqual(len(g[NEW_HIT]), 1)
        self.assertEqual(g[NEW_HIT][0]["before"], "(not screened)")

    def test_a_brand_new_party_that_is_clear_is_merely_added(self):
        before = load_dispositions(make_csv([]))
        after = load_dispositions(make_csv([row("C-9", "CLEAR")]))
        g = diff_dispositions(before, after)
        self.assertEqual(len(g[ADDED]), 1)
        self.assertEqual(len(g[NEW_HIT]), 0)

    def test_dropped_party_is_reported_not_ignored(self):
        before = load_dispositions(make_csv([row("C-1", "REVIEW")]))
        after = load_dispositions(make_csv([]))
        g = diff_dispositions(before, after)
        self.assertEqual(len(g[REMOVED]), 1)

    def test_unchanged_rows_do_not_leak_into_other_categories(self):
        rows = [row(f"C-{i}", "CLEAR") for i in range(5)]
        g = diff_dispositions(load_dispositions(make_csv(rows)),
                              load_dispositions(make_csv(rows)))
        self.assertEqual(len(g[UNCHANGED]), 5)
        for key in (NEW_HIT, RESOLVED, CHANGED, ADDED, REMOVED):
            self.assertEqual(g[key], [], key)

    def test_report_warns_that_a_new_hit_has_other_explanations(self):
        g = diff_dispositions(load_dispositions(make_csv([row("C-1", "CLEAR")])),
                              load_dispositions(make_csv([row("C-1", "REVIEW")])))
        md = diff_report(g, "a", "b")
        self.assertIn("not necessarily a new designation", md)
        self.assertIn("manifest digests", md)

    def test_report_renders_every_populated_category(self):
        before = load_dispositions(make_csv([row("C-1", "CLEAR"), row("C-2", "REVIEW"),
                                             row("C-3", "REVIEW")]))
        after = load_dispositions(make_csv([row("C-1", "BLOCKED"), row("C-2", "CLEAR"),
                                            row("C-4", "REVIEW")]))
        md = diff_report(diff_dispositions(before, after), "a", "b")
        for heading in ("## New hits", "## No longer hitting",
                        "## No longer in the party file"):
            self.assertIn(heading, md)

    def test_rows_without_a_ref_are_skipped_not_crashed_on(self):
        self.assertEqual(load_dispositions(make_csv([row("", "CLEAR")])), {})


class TestOpenCases(unittest.TestCase):
    def test_latest_run_wins_per_reference(self):
        runs = [
            ("20260101-000000", load_dispositions(make_csv([row("C-1", "CONFIRMED_HIT")]))),
            ("20260201-000000", load_dispositions(make_csv([row("C-1", "CLEAR")]))),
        ]
        md = open_cases_report(runs)
        self.assertIn("Nothing open", md)

    def test_a_case_open_only_in_the_latest_run_appears(self):
        runs = [
            ("20260101-000000", load_dispositions(make_csv([row("C-1", "CLEAR")]))),
            ("20260201-000000", load_dispositions(make_csv([row("C-1", "BLOCKED")]))),
        ]
        md = open_cases_report(runs)
        self.assertIn("C-1", md)
        self.assertIn("BLOCKED", md)

    def test_runs_are_ordered_by_label_not_by_input_order(self):
        later = ("20260201-000000", load_dispositions(make_csv([row("C-1", "CLEAR")])))
        earlier = ("20260101-000000", load_dispositions(make_csv([row("C-1", "BLOCKED")])))
        # Passed newest-first; the newest must still win.
        self.assertIn("Nothing open", open_cases_report([later, earlier]))

    def test_worst_disposition_sorts_first(self):
        runs = [("r1", load_dispositions(make_csv([
            row("C-1", "REVIEW"), row("C-2", "BLOCKED"), row("C-3", "ESCALATE")])))]
        md = open_cases_report(runs)
        self.assertLess(md.index("C-2"), md.index("C-3"))
        self.assertLess(md.index("C-3"), md.index("C-1"))


class TestPartyFileEncoding(unittest.TestCase):
    """ERP and Excel exports are routinely CP-1252, and those are exactly the
    files carrying the accented names this tool normalizes."""

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.dir.cleanup()

    def _write(self, data: bytes) -> Path:
        p = Path(self.dir.name) / "parties.csv"
        p.write_bytes(data)
        return p

    def test_utf8(self):
        p = self._write("name\nCafé Trading GmbH\n".encode("utf-8"))
        text, notes = read_party_file(p)
        self.assertIn("Café", text)
        self.assertEqual(notes, [])

    def test_utf8_with_bom(self):
        p = self._write("name\nMüller AG\n".encode("utf-8-sig"))
        text, notes = read_party_file(p)
        self.assertTrue(text.startswith("name"), "BOM was not stripped")
        self.assertIn("Müller", text)

    def test_cp1252_decodes_and_warns(self):
        p = self._write("name\nCafé Trading GmbH\nMüller Söhne AG\n".encode("cp1252"))
        text, notes = read_party_file(p)
        self.assertIn("Café", text)
        self.assertIn("Müller", text)
        self.assertTrue(any("not UTF-8" in n for n in notes))

    def test_undecodable_bytes_warn_loudly_about_the_match_risk(self):
        p = self._write(b"name\n\xff\xfe\x00Acme\n")
        text, notes = read_party_file(p)
        self.assertTrue(text)
        # Whatever encoding wins, a silent pass is the failure mode to avoid.
        self.assertTrue(notes, "a non-UTF-8 file produced no warning at all")

    def test_empty_file_does_not_crash(self):
        p = self._write(b"")
        text, notes = read_party_file(p)
        self.assertEqual(text, "")


if __name__ == "__main__":
    unittest.main()
