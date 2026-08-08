# Assurance case

This document is a claim-to-evidence map, not a certification. It prevents a
public description from outrunning the repository's actual enforcement.

| Claim | Enforced or demonstrated by | Residual limitation |
|---|---|---|
| Claude Code can discover the plugin and its two skills | Official manifest field shapes, schema URLs, marketplace-source tests, documented namespaced invocation | Full install smoke test requires a current Claude Code binary and network access |
| Extraction recipes are structurally reviewable | Draft 2020-12 schema, 100-entry backlog checks, filename/index parity, HTTPS/date/uniqueness bibliography tests | v0.7 does not fetch sources, type their authority, map individual claims to sources, or prove a route in any tenant |
| A non-unknown usage or verdict has cited evidence | JSON Schema conditionals and invalid fixtures | Schema validates presence/shape, not whether the citation is true or sufficient |
| Evidence lineage is explicit | Stable evidence IDs, `derived_from`, evidence class, coverage horizon, support scope | Independence and source correctness still require review |
| Missing observations are not automatically “never” | Coverage-horizon field plus skill rules and eval expectations | A reviewer can still misclassify an allegedly all-time source |
| Critical processes are computable graph objects | Business-process nodes, `supports` edges, graph schema, cross-artifact validator, synthetic example | The discovered graph can omit undocumented dependencies |
| Rebuild order is dependency-derived | Explicit interaction-to-dependency projection and SCC/topological procedure | Direction mapping and boundary completeness require spot checks |
| Tenant data is preserved independently of rebuild verdict | Preservation schema requires status, files/digests, and accepted gaps; the validator verifies containment, size, and SHA-256 | Vendor export limits can make a complete export impossible |
| Shareable paired cases received a separate sanitization review | Pair schema conditional requires approved review metadata | Metadata is not content inspection; re-identification risk remains contextual |
| Evaluation cases are isolated from training | Required dataset role and lineage group; the validator and negative tests reject cross-role overlap | External training pipelines must honor the recorded split |
| Historical replay is side-effect-free and version-aware | Replay context requires a legacy config reference and verified side-effect isolation | Capturing every hidden state variable is often impossible |
| Skill archives are reproducible from source | Deterministic packager, byte comparison in CI, SHA-256 manifest | Reproducibility does not by itself prove source trust or semantic correctness |
| Release artifacts came from this repository workflow | GitHub artifact attestation in the tag workflow | Consumers must actually verify the attestation and repository identity |
| The export-compliance deterministic core is tested on Python 3.11–3.14 | 274 unit/adversarial tests, hash-seed rerun, end-to-end fixture screen, cross-run disposition comparison | Fixture coverage is not legal certification or proof against all name variants |
| Export-compliance can run without outbound screening calls | Default offline backend and local fixture tests | `refresh` uses government endpoints; configured hosted model backends send minimized case data |

## Explicit non-claims

The repository does not claim:

- access to vendor source code or undocumented tenants;
- automatic support for every SaaS API or UI;
- that the recipe backlog is a market-adoption ranking, or that a
  `doc-derived-unverified` recipe is an exercised connector;
- proof that a feature is unused from a short or biased evidence window;
- causal savings from an observed process bottleneck;
- universal behavioral equivalence from a finite replay suite;
- that a skill alone is an appropriate replacement for shared transactional
  state, identity, statutory engines, or safety-critical controls;
- that `raw-local-only` describes the model or connector network boundary;
- legal advice, export authorization, or a compliance certification.

## Review rule

Any new quantitative, privacy, security, legal, compatibility, performance, or
“always/never” statement in public copy must land with one of:

1. a deterministic test or machine-enforced invariant;
2. a reproducible benchmark with environment and sample definition;
3. a primary-source citation and a clearly marked inference;
4. an explicit limitation adjacent to the claim.

If none applies, rewrite it as a hypothesis or remove it.
