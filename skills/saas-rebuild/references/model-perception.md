# Optional model perception with Jev/System One

Jev (TypeSafe System One) is an optional perception layer. It may classify,
score, prioritize, suggest, or veto an unsafe deterministic downgrade. It does
not own the recorded verdict, approve a sanitization, delete an edge, or prove
replay equivalence. Code continues to read counts, timestamps, digests, graph
structure, and acceptance thresholds; the model receives only minimized text.

## Authority rule

Apply model annotations through `tools/rules/raise_only.py`. A model result may
raise scrutiny or change `DROP` to `DEFER`. It must never lower scrutiny or
create a `DROP`, `KEEP`, approval, clearance, edge removal, or replay pass.
Until a question has a calibrated threshold on an eligible gold set, its
affirmative `flag`, `veto`, or `reject` signal is reduced to `prioritize`.
Negative answers remain inert. Choice questions act only on their catalog's
trigger options or contradictions with a local declared value (C2, E1, I2);
the declared value is never sent to the model.
The runner's policy API binds calibration to the returned model, exact question
hash, catalog version, validation reference, human approval, and a passing
canary for that model. It applies the isotonic probability before the threshold;
the uncertainty band adds review. Vetoes additionally require a separately
hashed paraphrase question to agree. The CLI supplies no authority policies,
so its high-authority answers remain prioritization only.
The former `ThresholdSet`/`CalibratedThreshold` types are accepted for routing
compatibility, but cannot grant authority because they lack the pinned provider
model, approval, validation reference, canary, and veto-twin bindings.

## Boundary contract

Every call requires a `model-vendor-review` preflight item with status `ready`
and a matching endpoint record in `teardown.json.data_boundary.model_endpoints`.
The record fixes the exact endpoint, approved purposes, allowed data classes,
contract status, and approver. The gate fails closed: restricted data requires
ZDR in force, PHI requires a BAA in force, and EU personal data requires a
recorded transfer mechanism.
Record `data_boundary.regulated_data` explicitly, for example
`{"phi":"no","eu_personal_data":"no"}` for synthetic data. Missing or
`unknown` declarations presume those categories are present. Per-item and CLI
privacy flags may raise those controls but cannot clear them.

Only server-side or CLI tooling may call Jev. The browser application makes no
Jev requests and never receives `TYPESAFE_API_KEY`.

## Running

Keep the API key in an ignored `.env` file as `TYPESAFE_API_KEY`; never add it
to teardown artifacts, logs, examples, or commits. Offline mode is the default
and performs no network or artifact writes:

```bash
python3 skills/saas-rebuild/tools/jev_run.py --mode offline examples/synthetic-crm
```

For an approved synthetic/public contract spike, use shadow mode with explicit
limits and `--allow-network`. A dollar cap also requires an explicitly supplied,
current verified input price. Inspect `model-annotations.jsonl` and the hash-chained
`.systemone/calls.jsonl`; shadow annotations have no operational effect.

```bash
python3 skills/saas-rebuild/tools/jev_run.py examples/synthetic-crm --mode shadow \
  --allow-network --limit 1 --max-calls 1 --max-input-tokens 20000 \
  --max-cost-usd 0.01 --price-per-million-input-tokens <verified-current-price>
```

The byte-based reservation allows for state billing per question and overhead.
Failed attempts consume the call reservation, and budgeted requests never
silently retry. These are per-run local controls; they do not enforce an
account-wide monthly limit or know about usage elsewhere. Use the provider's
account cap for the monthly $5 constraint. No account setting is changed by
this tool.

Replay reads the cache and restores the original annotations, including run ids,
effects, timestamps, and call-log sequence. Repeated writes deduplicate them.
Replay itself never appends annotation records, including when the original run
had authority; its returned records are historical results for inspection.
A miss or old cache without frozen annotations fails without a network call.
The strengthened cache format intentionally does not accept the old prototype
cache. Keep old records as evidence; do not relabel them as new recordings.

## Local demo and decision review

From the repository root, run this once with a new output directory:

```bash
python3 scripts/demo_jev.py .jev-demo
python3 skills/saas-rebuild/tools/validate_artifacts.py .jev-demo
python3 skills/saas-rebuild/tools/jev_report.py .jev-demo
```

The demo copies the synthetic CRM and injects the committed, historical Jev
response through a fake transport. It needs no key, makes no network request,
costs nothing, verifies the audit chain and exact replay, and writes
`.jev-demo/jev-review.json`. It never overwrites an existing directory.

The read-only report compares recorded verdicts with deterministic proposals and
open annotations. It preserves the baseline reason when a flag/veto holds a
DROP as DEFER. Existing synthetic citations lack structured `measure` values,
so their prose counts cannot establish deterministic use: the report explicitly
defers those entries rather than inventing measurements. Human review remains
required for DROP, DEFER, undefined cells, and model review items.

## Inputs for each question set

Feature perception reads classified feature inventory fields automatically.
The existing citation and graph readers are preserved: without a supplemental
registry they inspect citation metadata and ordered graph evidence, keeping
declared classes/types local for comparison. A source pointer by itself cannot
prove claim support; supply actual excerpts for that assessment.
For richer context and the remaining sets, use `model-inputs.jsonl`, one bounded item per line. Classify that
file under `data_boundary.source_classes` and classify every supplied field;
missing classifications are restricted. For example:

```json
{"question_set":"citation-checks","target_id":"ev-search-runtime","fields":{"source_text":"Customer lookup is an observed service action."},"field_classes":{"source_text":"public"},"contains_phi":false,"contains_eu_personal_data":false}
```

That example shows the format only; source text must be an actual authorized
excerpt in an engagement. The original claim comes from the registered citation.

| Set | Target registry | Allowed fields |
|---|---|---|
| citation-checks | Inventory evidence id | claim (read from inventory), scope, source_text |
| graph-edges | `from\|to\|type` in graph.json | source_label, target_label, script_body, deployment_text |
| process-mining | Distinct event signature id in model-inputs | description, control, activity_labels |
| sanitization | Pair id in pairs.jsonl | input, output (read from pair; overrides ignored) |
| replay-residuals | Residual id in model-inputs | difference, registered_divergences, legacy_notes |
| interviews | Statement id in model-inputs | statement, candidate_features |

Supplemental event signatures, residuals, and interview ids also let the artifact
validator resolve those annotations. Duplicate ids within a question set fail.
Holdout pairs cannot receive model assistance. PHI/EU flags propagate through
the runner to the contract gate; whole-run flags are available on the CLI too.
The default catalogs provide bounded suggestions; domain-specific target choices
still need a reviewed catalog and new hashes/calibration.

The conventional `model-annotations.jsonl` sidecar is discovered even without
the optional `artifacts.model_annotations` pointer, keeping evidence artifacts
unchanged. When supplied, that pointer must resolve to the same validated file.

## Gold-set separation

Never use model-assisted artifacts as calibration or holdout gold. Training,
calibration, and holdout split groups remain disjoint. Human-reviewed
annotations record acceptance or rejection separately from the model answer;
the original answer is immutable.
