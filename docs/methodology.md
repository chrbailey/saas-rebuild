# Method and intellectual lineage

## Abstract

SaaS Rebuild treats tenant reconstruction as a partially observed system-
identification problem under authorization, data-governance, and migration
constraints. The object of study is not the vendor's complete product. It is a
tenant-specific operational system:

\[
\mathcal{T} = (C, D, W, I, H, P)
\]

where \(C\) is configuration, \(D\) is data and state, \(W\) is observed
workflow behavior, \(I\) is the integration boundary, \(H\) is human practice
including workarounds, and \(P\) is the commercial/policy envelope. The method
builds an evidence-bearing approximation \(\hat{\mathcal{T}}\), chooses which
capabilities merit replacement, and verifies a target system against held-out
behavioral cases.

The approximation is unavoidably incomplete. Missing telemetry, censored
history, unobserved seasonal behavior, undocumented integrations, mutable
configuration, and interview bias are modeled as uncertainty—not silently
converted into absence.

## Where this sits

| Adjacent field | What it normally optimizes | What SaaS Rebuild adds |
|---|---|---|
| SaaS management | Spend, seats, renewals, portfolio redundancy | Feature/process evidence and replacement design |
| Task/process mining | Observed paths and bottlenecks | Configuration, preservation, dependency graph, target architecture |
| Application intelligence | Source-code and data dependencies | Tenant behavior when vendor source is unavailable |
| Migration tooling | Data or code transformation | Used-vs-unused decisions and behavior-level acceptance |
| Agent/skill authoring | Reusable model instructions | Evidence acquisition, provenance, holdouts, and cutover gates |

No single row is a direct substitute. The method is a synthesis across them.

## Epistemic model

### Claims and citations

A conclusion is represented as a claim supported by one or more citations.
Each citation records:

- a stable evidence identifier;
- evidence class: structure, runtime, or human/framing;
- acquisition plane and precise source;
- observation time and coverage horizon;
- confidence and sensitivity;
- derivation parents, so restatements of one source are not counted as
  independent corroboration;
- which conclusion fields it supports.

This is a deliberately smaller, JSON-native specialization of provenance
concepts in [W3C PROV-DM](https://www.w3.org/TR/prov-dm/). It is not advertised
as a full PROV implementation.

Extraction recipes sit outside this tenant evidence model. They are priors
about where authorized evidence may be acquired, based on a dated
bibliography. A recipe becomes evidence only when a route is re-verified and
the resulting artifact receives a tenant evidence ID, coverage horizon, and
acquisition record. The v0.8 recipe format does not yet encode claim-level
source references; the assurance case records that limitation.

### Absence is bounded

Let \(O_f(W)\) mean that feature \(f\) was observed in evidence window \(W\).
For a bounded window, \(\neg O_f(W)\) means only “not observed in \(W\).” It
does not imply that \(f\) is never used. A `never` conclusion needs evidence
whose horizon covers the relevant lifetime or business cadence, and even then
must survive checks for archival, purge, integration-only, and seasonal paths.

### Evidence independence

Two extracts of the same underlying table are not two independent signals.
Derivation chains are collapsed before corroboration is counted. Independence
means distinct provenance, not distinct file formats or extraction routes.

### Observational, not causal

Process mining finds associations in event logs. A long wait edge is a
bottleneck candidate, not proof that automating that transition will recover
the observed hours. Calendar effects, batching, staffing, upstream quality,
and policy holds can confound the relationship. `median_wait × case_count` is
reported as an exposure score, not causal savings.

## Behavioral cases and leakage control

Historical input/output cases can support three different purposes:

1. development and behavior cloning;
2. deterministic regression;
3. held-out evaluation.

Those purposes are not interchangeable. A case used for training cannot be
presented later as independent evidence of model generalization. Cases are
partitioned by a stable lineage group—customer, workflow instance, period, or
another leakage boundary—before training. `holdout-eval` groups remain
immutable and excluded from training. Analyst judgments are never evaluation
gold; only system-of-record, observed-UI, or parallel-run-validated labels can
qualify.

Replay also requires configuration and state context. A legacy system is not a
pure function: rates, balances, periods, sequence numbers, feature flags, and
historical scripts influence outputs. Cases are partitioned at configuration
changes, state capture is recorded, and replay is side-effect-free.

## Architecture selection

Each retained capability is classified by state, concurrency, determinism,
integration, and control requirements. The target follows from that shape:

- reasoning/document behavior → skill;
- deterministic transform → library or service;
- shared mutable state → application and database;
- cross-system event flow → integration/workflow runtime;
- high-impact decision → deterministic constraints and accountable approval.

The result may be smaller than the source SaaS without being simplistic.
Complexity is removed only when evidence shows that the organization does not
need it or can replace it with a more explicit component.

## Graph semantics

The observed interaction graph and the build-dependency graph are different
objects. Runtime edges describe who reads, writes, triggers, joins, exports, or
supports whom. A dependency projection then orients prerequisite edges for
sequencing. Topologically sorting the raw interaction graph is invalid because
`reads` and `writes` do not share a universal build direction.

Business processes are explicit graph nodes. Without them, a “minimal feature
cover of critical processes” is not computable; criticality would remain an
unstructured adjective.

## Acceptance

For a held-out case \(x\), let \(L_v(x, s)\) be the legacy output under legacy
version/configuration \(v\) and captured state \(s\), and \(R(x)\) the rebuild
output. An observed difference is classified before acceptance:

\[
\Delta(x) = \operatorname{diff}(R(x), L_v(x,s))
\]

- no difference: legacy-equivalent for the asserted fields;
- registered difference: an intended, evidence-backed simplification recorded
  before replay;
- legacy defect: source output is wrong and the case is excluded from gold;
- unexplained difference: milestone failure.

Passing finite replay cases does not prove universal equivalence. It supplies
bounded evidence whose coverage, state assumptions, and exclusions remain
inspectable.

## Failure conditions

Stop or downgrade conclusions when any of these holds:

- authorization or contractual scope is unresolved;
- the actual model/connector data boundary is not approved;
- preservation cannot finish before the retrieval deadline;
- runtime evidence cannot cover the feature's plausible cadence;
- event logs lack a stable case notion or interpretable timestamps;
- integration inventory is incomplete at a proposed cut boundary;
- historical configuration/state cannot support meaningful replay;
- held-out lineages were exposed to training or design selection;
- a required transactional/control capability is being forced into a prompt-
  only target.

The correct output in these conditions is `DEFER`, a narrower claim, or a
different architecture—not manufactured certainty.
