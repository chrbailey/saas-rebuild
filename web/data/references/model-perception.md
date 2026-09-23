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
`flag`, `veto`, or `reject` authority is reduced to `prioritize`.

## Boundary contract

Every call requires a `model-vendor-review` preflight item with status `ready`
and a matching endpoint record in `teardown.json.data_boundary.model_endpoints`.
The record fixes the exact endpoint, approved purposes, allowed data classes,
contract status, and approver. The gate fails closed: restricted data requires
ZDR in force, PHI requires a BAA in force, and EU personal data requires a
recorded transfer mechanism.

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
hard limits. Inspect `model-annotations.jsonl` and the hash-chained
`.systemone/calls.jsonl`; shadow annotations have no operational effect.

```bash
python3 skills/saas-rebuild/tools/jev_run.py --mode shadow \
  --max-calls 1 --max-input-tokens 2000 examples/synthetic-crm
```

Replay mode reads the content-addressed cache and refuses a cache miss. Live
mode remains raise-only and should not be enabled until calibration gates pass.

## Gold-set separation

Never use model-assisted artifacts as calibration or holdout gold. Training,
calibration, and holdout split groups remain disjoint. Human-reviewed
annotations record acceptance or rejection separately from the model answer;
the original answer is immutable.
