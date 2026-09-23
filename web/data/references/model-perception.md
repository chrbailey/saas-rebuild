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

An effect follows the answer, never just the question. A Noul answer is the
probability that the question holds. A Choice answer counts only the options
its catalog entry names, in one of two ways. A `trigger` lists fixed options.
A `compare` maps each declared value of a target field to the options that
contradict it; the runner reads that value from the target, never sends it to
the model, and acts on the contradicting options' probability. A Choice
question with neither can suggest its answer but cannot flag, veto, reject, or
prioritize anything, and a comparator whose declared value is absent or
unmapped gives no signal.

`flag`, `veto`, and `reject` fire only when the answer's calibrated probability
meets a fitted threshold, and the annotation records both `calibrated_p` and
`threshold_set_id`; the annotation schema refuses those effects without them. A
threshold is bound to the hash of the question text it was fitted on, so editing
a question silently drops its calibration rather than reusing it. Until a
question has such a threshold on an eligible gold set, an affirmative answer
(probability at least 0.5) is reduced to `prioritize` and a negative one has no
effect. That cutoff only routes review work; it never gates a veto.

Three questions use comparators. C2 flags a citation whose text reads as a
different evidence class than it declares, such as configuration cited as
runtime evidence. E1 flags a directional edge whose text runs the other way;
`joins-on` is symmetric and never contradicts. I2 flags an interview claim at
least two frequency bands from observed usage, or `never` against any use.

## Boundary contract

Every call requires a `model-vendor-review` preflight item with status `ready`
and a matching endpoint record in `teardown.json.data_boundary.model_endpoints`.
The record fixes the exact endpoint, approved purposes, allowed data classes,
contract status, and approver. The gate fails closed: restricted data requires
ZDR in force, PHI requires a BAA in force, and EU personal data requires a
recorded transfer mechanism.

Declare PHI and EU personal data in `data_boundary.regulated_data` as `yes`,
`no`, or `unknown`. Only an explicit `no` clears a category: an absent
declaration or `unknown` is treated as present, so the BAA and transfer gates
engage. The validator applies the same rule to every recorded annotation, and
the runner refuses a client aimed at any endpoint other than the approved one.

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

Replay mode reads the content-addressed cache, refuses a cache miss, and
reproduces the cached answers for audit. It carries no authority and appends no
annotations, so replaying a shadow spike cannot turn it into effects that no one
approved. Live mode remains raise-only and should not be enabled until
calibration gates pass; `jev_run.py` does not yet load a threshold set, so its
live runs can only prioritize or suggest.

## Gold-set separation

Never use model-assisted artifacts as calibration or holdout gold. Training,
calibration, and holdout split groups remain disjoint. Human-reviewed
annotations record acceptance or rejection separately from the model answer;
the original answer is immutable.
