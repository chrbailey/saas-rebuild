# Dependency Graph — deriving the rebuild instead of guessing it

Phase 1b already collected every node and edge; this file assembles them into
a directed typed graph and computes five results from it. The point: rebuild
milestones, the risk register, and the minimal KEEP set become *derived
artifacts with evidence trails*, not judgment calls. Build the graph after
Phase 1b completes, use it during Phase 3 verdicts and Phase 5 sequencing.

## Node and edge taxonomy

Five node types: **feature**, **entity**, **script** (automation/workflow),
**integration**, **report**. Reuse feature ids from `teardown.json`; entity
ids are the data_entities strings, kebab-cased.

Five edge types, all directed, all typed:

- `reads` — X consumes data from entity Y
- `writes` — X creates/updates records in entity Y
- `triggers` — X fires script/automation Y (record save, schedule, webhook)
- `joins-on` — report/search X joins entity Y to entity Z (edge per entity)
- `exports-to` — X ships data to integration Y (API, iPaaS flow, file drop)

Each Phase 1b plane supplies specific edge types — record the plane on every
edge (same plane names as the evidence enum in
`templates/feature-inventory.schema.json`):

- **config-census** → feature→entity edges (forms bind fields to entities;
  workflows declare their record types) and entity→entity via custom-field
  references
- **code-analysis** → script edges: the trigger+entities+external-calls
  summary per script converts directly to `triggers`, `reads`, `writes`
- **integration-inventory** → `exports-to` edges from API logs, iPaaS flow
  definitions, and scheduled file drops
- **report definitions** (saved searches, report builder) → report→entity
  `reads` and `joins-on` edges

One honest rule, stated up front: **an absent edge means absent evidence,
not independence.** Undocumented integrations are the classic silent edge —
file drops and shared-drive CSVs never show in API logs. Any integration
node with zero discovered edges gets flagged `edges-unverified` and carried
into the risk register. Never prune it; a bare integration node is a finding,
not noise.

## Construction

Write `graph.json` in the teardown output dir alongside `teardown.json`:

```json
{"nodes": [
   {"id": "invoice", "type": "entity", "label": "Invoice"},
   {"id": "aging-report", "type": "report", "label": "AR Aging"},
   {"id": "late-fee-script", "type": "script", "label": "Late fee calc"},
   {"id": "qbo-sync", "type": "integration", "label": "QuickBooks sync"}],
 "edges": [
   {"from": "aging-report", "to": "invoice", "type": "reads",
    "evidence_plane": "config-census"},
   {"from": "invoice", "to": "late-fee-script", "type": "triggers",
    "evidence_plane": "code-analysis"},
   {"from": "late-fee-script", "to": "invoice", "type": "writes",
    "evidence_plane": "code-analysis"},
   {"from": "late-fee-script", "to": "qbo-sync", "type": "exports-to",
    "evidence_plane": "integration-inventory"}]}
```

A pure-Python adjacency dict is enough for every computation below:
`adj = {n: [] for n in nodes}; for e in edges: adj[e["from"]].append(e)`.
Use networkx **if already available** — never install it, nothing here may
require it. Every algorithm below fits in a dozen lines of stdlib Python.

Expect a few hundred nodes and low thousands of edges on a mid-size tenant;
all of these computations are instant at that scale. If deduping edges,
merge evidence planes into a list — two planes agreeing on one edge is
stronger evidence, not a duplicate.

## The five derived results

### 1. Load-bearing entities → Phase 5 schema order

Weighted in-degree over edges pointing *at* each entity: `writes` = 3,
`joins-on` = 2, `reads` = 1 (a written entity is upstream state; a read one
may be reference data). PageRank on the reversed graph if networkx exists —
rankings rarely differ enough to matter; say which you used.

Feeds: the top entities by score get their JSON schemas designed **first**
in Phase 5 — they are the walking skeleton's data model. An entity that
scores high but carries no KEEP feature is itself a finding (something
depends on data nobody claims to use — usually an integration).

### 2. Articulation points → risk register

Nodes whose removal disconnects the (undirected view of the) graph. These
are the pre-identified landmines: "breaking an unknown integration is the
classic rebuild failure" is exactly an articulation point you didn't compute.
Standard DFS sketch:

```python
def articulation_points(adj):  # adj: undirected {node: set(neighbors)}
    disc, low, ap, t = {}, {}, set(), [0]
    def dfs(u, parent):
        disc[u] = low[u] = t[0]; t[0] += 1; children = 0
        for v in adj[u]:
            if v not in disc:
                children += 1; dfs(v, u)
                low[u] = min(low[u], low[v])
                if parent is not None and low[v] >= disc[u]: ap.add(u)
            elif v != parent: low[u] = min(low[u], disc[v])
        if parent is None and children > 1: ap.add(u)
    for n in adj:
        if n not in disc: dfs(n, None)
    return ap
```

Feeds: **every articulation point gets an explicit bridge-or-replace line in
the risk register — never silence.** Either the rebuild replaces it inside a
milestone, or a bridge (CSV/API shim) holds the two sides together during
transition. "We'll deal with it later" is not one of the two options.

### 3. Capability islands → strangler-fig milestones

Connected components of the subgraph induced by KEEP/SIMPLIFY nodes (plus
the entities they touch). These components ARE the strangler-fig milestones:
each island can be rebuilt, parallel-run, and cut over independently because
nothing kept crosses its boundary.

The check that matters: **if the whole KEEP set is one giant component,
don't invent milestone boundaries by feel** — look for cut edges (bridges)
where a CSV bridge can sever the component into phases. A single `reads`
edge between two clusters is a nightly CSV export; a `writes` edge is a
harder, two-way bridge. No severable edge at all means those capabilities
genuinely ship together — say so in the plan rather than pretending.

Feeds: Phase 5 milestone list, one milestone per island (or per severed
sub-island), bridges named per cut edge.

### 4. Rebuild order → milestone sequencing

Topological sort of the condensed component DAG. Condense cycles first
(strongly connected components — Tarjan, or networkx `condensation`): **a
cycle means those pieces ship in one milestone**; there is no order inside
mutual dependence, and pretending otherwise produces a milestone that can't
pass its own verification step. Then topo-sort the condensed DAG: upstream
components (written-to entities, triggering scripts) rebuild before their
dependents.

Feeds: the order of the Phase 5 milestone list. Ties broken by island
score — highest load-bearing entity first.

### 5. Minimal KEEP cover → verdict challenge

Set-cover framing: the smallest set of features whose union of entity and
process coverage still supports every critical business process (criticality
`critical` from Phase 3). Greedy approximation — repeatedly take the feature
covering the most uncovered processes — is fine and is what to use; exact
set cover is NP-hard and the graph is small enough that greedy lands within
a feature or two of optimal. Say it's greedy in the artifact.

Feeds: **every KEEP verdict outside the cover gets re-challenged**: "what
breaks if this goes?" If the answer cites no critical process and no edge
into the cover, the honest verdict is SIMPLIFY or DROP with the graph as
cited evidence. The cover doesn't overturn verdicts by itself — it names
which ones must re-defend themselves.

## Joining verdicts onto the graph

After Phase 3, color every node with its verdict. The findings live in the
mismatches, not the agreements:

- **DROP node that a kept articulation point (or any KEEP path) depends
  on**: not droppable *yet*. The verdict stands — the **sequencing**
  changes: DEFER the removal to the milestone where its dependents' bridge
  lands, and record the dependency edge as the reason. Silent early removal
  here is how rebuilds break integrations nobody knew existed.
- **KEEP island no critical process touches**: a KEEP to re-challenge (see
  result 5). Often it's a departmental habit, not a requirement.
- **DEFER node upstream of milestone-1 nodes**: the deferral blocks the
  first milestone; either pull it forward or bridge around it, explicitly.

Update `teardown.json` decisions with any verdict or sequencing change,
citing the graph edge(s) that forced it.

## Critic checks (run before any ranking or verdict change ships)

1. **Edge direction errors invert every centrality conclusion.** A `reads`
   edge recorded backwards turns a reference table into a load-bearing hub.
   Spot-check five edges against their source plane — open the actual form
   definition, script summary, or flow config — before trusting any ranking.
2. **Report-derived edges overcount.** Every saved report declares entity
   reads, including the dozens nobody has opened in years. Weight report
   edges by the report's own usage evidence (last-run telemetry, recipient
   interviews) or the top of the load-bearing ranking fills with entities
   that only dead reports touch.
3. **The graph is config-time truth.** It shows what *could* flow, not what
   does. Same STRUCTURE+RUNTIME join rule as Phase 3: before any verdict
   changes on graph evidence, join the edge with runtime evidence
   (transactions, execution logs, telemetry). A structural edge alone
   defends sequencing decisions (don't break what might be live); it never
   alone promotes a feature to "used."

Retract in place if a check fails, keep the retraction visible, and rerun
the derived results — a handful of corrected edges can reorder milestones.
