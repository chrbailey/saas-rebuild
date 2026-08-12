# Dependency graph — observation, projection, and rebuild sequencing

The teardown graph has two distinct semantics:

1. the **interaction graph** records evidence about the tenant as observed;
2. the **build-dependency projection** orients prerequisites for the proposed
   target architecture.

Never topologically sort the raw interaction graph. A `reads` edge and a
`writes` edge both point from an actor to an entity, but their data-flow and
build-prerequisite interpretations differ. Treating them as one generic
dependency direction can produce a plausible, reversed migration plan.

Write the interaction graph to `graph.json` and validate it against
`templates/dependency-graph.schema.json`. Derive the projection reproducibly
and record its algorithm version and sensitivity parameters.

## Interaction-graph contract

Six node types:

- `feature` — a user-visible or administrable capability;
- `business-process` — a named outcome such as order-to-cash;
- `entity` — durable or reference data;
- `script` — automation or workflow code;
- `integration` — an external boundary;
- `report` — a query or rendered information product.

Six directed edge types. Direction is part of the contract:

| Edge | Direction | Meaning |
|---|---|---|
| `reads` | actor → entity | Actor consumes entity state |
| `writes` | actor → entity | Actor creates or changes entity state |
| `triggers` | source → handler | Source event invokes a script or automation |
| `joins-on` | report → entity | Report joins the entity |
| `exports-to` | producer → integration | Producer sends data across a boundary |
| `supports` | capability → business process | Capability contributes to a named process |

Every edge carries `runtime_status`:

- `observed` — runtime evidence shows the interaction occurred;
- `structural-only` — configuration or code declares it, but runtime execution
  has not been established;
- `unknown` — evidence is ambiguous or the relevant window is inadequate.

Every edge also lists stable `evidence_ids` that resolve to citations in the
feature inventory or teardown evidence base. Duplicate observations of the
same underlying source are connected by `derived_from`; do not count them as
independent corroboration.

Example:

```json
{
  "schema_version": "0.7.0",
  "nodes": [
    {"id":"invoice","type":"entity","label":"Invoice"},
    {"id":"aging-report","type":"report","label":"AR aging","verdict":"KEEP"},
    {"id":"late-fee-script","type":"script","label":"Late-fee calculation","verdict":"SIMPLIFY"},
    {"id":"qbo-sync","type":"integration","label":"Accounting sync","edges_unverified":false},
    {"id":"collect-cash","type":"business-process","label":"Collect cash","critical":true}
  ],
  "edges": [
    {"from":"aging-report","to":"invoice","type":"reads","runtime_status":"observed","evidence_ids":["ev-report-run"]},
    {"from":"late-fee-script","to":"invoice","type":"writes","runtime_status":"observed","evidence_ids":["ev-script-log"]},
    {"from":"late-fee-script","to":"qbo-sync","type":"exports-to","runtime_status":"structural-only","evidence_ids":["ev-flow-config"]},
    {"from":"aging-report","to":"collect-cash","type":"supports","runtime_status":"observed","evidence_ids":["ev-collector-interview"]}
  ],
  "derived": {
    "generated_at":"2026-01-01T00:00:00Z",
    "algorithm_version":"interaction-projection-1",
    "sensitivity_parameters":{"structural_edges_included":true}
  }
}
```

An absent edge means absent evidence, not independence. File drops, shared-drive
CSVs, browser extensions, email rules, and personal automation may never appear
in API logs. Mark a known integration with no verified incident edges as
`edges_unverified: true` and carry it into the risk register.

## Evidence acquisition by plane

- `config-census`: feature/form bindings, declared workflow record types,
  entity references, report definitions;
- `code-analysis`: triggers, entity reads/writes, external calls;
- `integration-inventory`: API calls, iPaaS definitions, webhooks, schedules,
  file drops;
- `telemetry` and `transactional`: runtime promotion from `structural-only` to
  `observed` for the covered window;
- `interview`, `contract`, and `document`: business-process framing and
  candidate `supports` edges, preferably corroborated by runtime evidence.

Spot-check edge direction against the source artifact during construction.
Schema validity cannot detect a semantically reversed edge.

## Interaction-to-dependency projection

Define a new directed graph (D), where `A → B` means “A's target contract or
implementation is a prerequisite for B.” Apply an explicit rule table; do not
infer orientation from the raw arrow alone.

| Interaction edge | Default prerequisite edge | Rationale |
|---|---|---|
| actor `reads` entity | entity → actor | Reader needs the entity contract |
| actor `writes` entity | entity → actor | Writer needs storage and write contract |
| report `joins-on` entity | entity → report | Query depends on entity schema |
| source `triggers` handler | source → handler | Handler depends on source event contract |
| producer `exports-to` integration | producer → integration | Adapter depends on producer output contract |
| capability `supports` process | capability → process | Process acceptance depends on capability |

These are defaults, not universal laws. A target may introduce a canonical
event schema, anti-corruption layer, or bridge that changes prerequisites.
Record every override as a teardown decision with evidence and rationale.

Include `structural-only` edges conservatively for risk analysis. For cutover
ordering, calculate both (a) observed-only and (b) observed plus structural
projections. A plan whose ordering changes materially between them is
evidence-sensitive and needs dependency discovery before commitment.

Condense strongly connected components in the **projected graph**, then
topologically sort its condensation DAG. A cycle says those target contracts
are mutually dependent under the present design; it may indicate one milestone
or a missing interface, not an automatic command to ship every source node
together.

## Derived analyses

### 1. Load-bearing entities

Rank entities by incoming interaction demand: `writes` weight 3, `joins-on` 2,
and `reads` 1 as a documented default. Rerun at least one alternative such as
2/1/1 and report rank stability. Centrality is a prioritization heuristic, not
criticality proof. Dead reports and generated scripts can otherwise make an
unused entity appear central.

Use stable high-ranked entities to order schema and storage design. Challenge a
high-ranked entity with no retained consumer: it may expose an unknown
integration, a stale artifact, or bad evidence.

### 2. Articulation and cut risk

Compute articulation points and bridges on the undirected interaction view to
find discovered single points of connectivity. Treat them only as risk
candidates: missing edges can hide a real articulation point, and an incidental
structural edge can create a false one.

Every proposed migration boundary gets a boundary interrogation: inspect API
logs, schedules, service accounts, webhooks, file drops, shared folders, and
owner interviews. Name the target bridge or replacement and its rollback.

### 3. Capability islands

Connected components of retained capabilities and the entities they touch are
candidate strangler milestones. They are not proven independent merely because
the discovered graph is disconnected. Require:

- no unresolved `edges_unverified` node on the boundary;
- a defined interface for every crossing edge;
- observable parallel-run acceptance;
- a rollback path.

If the retained graph is one giant component, examine cut edges and interface
seams. A read-only reference edge may admit a snapshot bridge; shared writes
usually require a stronger consistency design.

### 4. Rebuild order

Sequence the condensed projected dependency graph, not the raw graph. For each
milestone, emit:

- prerequisites and interface versions;
- included target components;
- boundary bridges;
- acceptance cases and rollback;
- observed-only vs conservative ordering difference.

Ties may be broken by value, risk, preservation deadlines, or stable entity
rank, but the criterion must be recorded.

### 5. Critical-process coverage

Business processes are graph nodes, not prose labels. A direct or validated
path of `supports` edges maps capabilities to processes. First specify the
acceptance predicate for each critical process; many processes require an
**AND-set** of capabilities, so ordinary set cover can be unsound.

Use greedy set cover only as a challenge heuristic where one-capability
coverage is genuinely substitutable. Otherwise solve the small constrained
selection problem explicitly or enumerate candidate bundles. Every KEEP
capability outside all minimal accepted bundles is re-challenged; the graph
does not overturn its verdict by itself.

## Verdict joins

After Phase 3, join verdicts onto nodes and inspect mismatches:

- a DROP node required by a retained projected path keeps its product verdict,
  but removal is deferred until a bridge or replacement lands;
- a KEEP island with no validated path to a critical process must defend its
  value with other evidence;
- a DEFER prerequisite blocks its dependent milestone unless an explicit bridge
  isolates it;
- a structural-only edge may constrain safe sequencing without promoting its
  feature to “used.”

Record verdict and sequencing changes in `teardown.json.decisions`, citing the
forcing evidence IDs.

## Critic checks

Before publishing derived results:

1. Spot-check at least five raw edges and every proposed boundary edge against
   its source.
2. Collapse citation derivation chains before counting corroboration.
3. Down-weight or remove report edges whose own runtime status is unknown.
4. Compute observed-only and conservative sensitivity runs.
5. Verify every critical process has an explicit acceptance predicate.
6. Re-interrogate integration boundary nodes for unlogged transports.
7. Recompute every derived result after any edge correction and retain the
   superseded result as an auditable retraction.

The graph is a model of discovered evidence, not the tenant itself. Its value is
that assumptions, uncertainty, and projection rules are inspectable.
