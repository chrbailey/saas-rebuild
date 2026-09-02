# Migrating protocol artifacts from v0.7 to v0.8

Version 0.8 keeps the v0.7 artifact shapes and makes the validator enforce
more of what v0.7 only described. Most v0.7 artifacts migrate by fixing the
items below and then setting `schema_version` to `"0.8.0"`. Do not relabel
first and fix later: the validator reads the version and applies the v0.8
rules.

## Dates and timestamps

Every date is an anchored calendar date (`YYYY-MM-DD`, month 01–12, day
01–31) and every timestamp an anchored RFC 3339 value. A coverage window such
as `2026-06-01 or thereabouts`, a month of `13`, or trailing text after an
`as_of` now fails schema validation. Fix the value; do not widen the pattern.

## Pair citations

A citation carried by a pair in `pairs.jsonl` must resolve to an evidence
identity defined in `feature-inventory.json`, and every field of that
citation other than `evidence_id` must equal the inventory definition. A
paraphrased claim, a different coverage window, or a different evidence
class on the pair's copy is now an error. `derived_from` parents must resolve
to known evidence ids. Copy the inventory citation verbatim, or define a new
evidence id in the inventory.

## Teardown state and graph

`teardown.json` must name the artifact files the validator checked
(`feature-inventory.json`, `pairs.jsonl`); pointing `pairs` at another file
is an error. Decision `evidence_ids` must resolve. A graph feature node must
have an inventory entry, and a node verdict must match its feature's verdict
in both directions — a node with a verdict its feature lacks fails.

## Preservation manifest

File paths are compared after resolution, so `./pairs.jsonl` and
`pairs.jsonl` are the same file; a replay-corpus `record_count` is checked
against the pairs file whichever spelling the manifest uses.

## Extraction recipes

`schema_version` becomes `"0.8.0"`. Research-process caveats (a vendor page
that could not be fetched, a limit read from a secondary source) belong in
the new optional `research_caveats` array, not in `export_rights.summary`
or `notes`; a test rejects session or environment language in those data
fields.

## Reference implementation

The export-compliance engine is at 1.3.0 and its skill at 0.3.0. A
pre-0.2.0 `lists/` snapshot has no corpus digest and is refused until
`xscreen refresh` is re-run; matching scores are not comparable across the
engine bump. See `skills/export-compliance/references/benchmark.md` for the
measured effect.
