# Assurance case

This document is a claim-to-evidence map, not a certification. It prevents a
public description from outrunning the repository's actual enforcement.

| Claim | Enforced or demonstrated by | Residual limitation |
|---|---|---|
| The browser workspace keeps the API key in the browser and sends it only to Anthropic | `web/app.js` stores the key in `localStorage`, calls `api.anthropic.com` directly with the documented browser-access header, and has no server component; the static deployment has no build step and no environment variables | Everything pasted into the chat reaches Anthropic under the user's own key and account terms; the workspace cannot attest to what the model provider retains |
| Claude Code can discover the plugin and its two skills | Official manifest field shapes, schema URLs, marketplace-source tests, documented namespaced invocation | Full install smoke test requires a current Claude Code binary and network access |
| Extraction recipes are structurally reviewable | Draft 2020-12 schema, 100-entry backlog checks, filename/index parity, HTTPS/date/uniqueness bibliography tests | v0.8 does not fetch sources, type their authority, map individual claims to sources, or prove a route in any tenant |
| A non-unknown usage or verdict has cited evidence | JSON Schema conditionals and invalid fixtures | Schema validates presence/shape, not whether the citation is true or sufficient |
| Evidence lineage is explicit | Stable evidence IDs, `derived_from`, evidence class, coverage horizon, support scope | Independence and source correctness still require review |
| Every citation outside the feature inventory resolves to it | The validator resolves graph-edge, teardown-decision, and pair evidence IDs against the inventory, requires a pair's copy of a citation to equal its inventory definition field for field, and resolves `derived_from` parents; one negative test per rule | Resolution proves the citation was recorded, not that it is true or sufficient |
| Missing observations are not automatically “never” | Coverage-horizon field plus skill rules and eval expectations | A reviewer can still misclassify an allegedly all-time source |
| Critical processes are computable graph objects | Business-process nodes, `supports` edges, graph schema, cross-artifact validator, synthetic example | The discovered graph can omit undocumented dependencies |
| Graph verdicts mirror the inventory | The validator compares feature and node verdicts in both directions (a node verdict its feature lacks fails too) and rejects feature nodes with no inventory entry; negative tests | A verdict that is wrong in both places is consistent and passes |
| Contract dates and timestamps are calendar-plausible | Anchored `YYYY-MM-DD` and RFC 3339 patterns in all five artifact schemas; pattern tests reject month 13, day 32, hour 24, and trailing text | Patterns do not check day against month (2026-02-31) or leap years |
| Rebuild order is dependency-derived | Explicit interaction-to-dependency projection and SCC/topological procedure | Direction mapping and boundary completeness require spot checks |
| Tenant data is preserved independently of rebuild verdict | Preservation schema requires status, files/digests, and accepted gaps; the validator verifies containment, size, SHA-256, replay-corpus record count, and duplicate listings by resolved path (a `./` spelling cannot bypass them); negative tests | Vendor export limits can make a complete export impossible |
| `teardown.json` declares the artifacts that were validated | The validator requires each declared artifact path to resolve to the file it checked; negative test | The rebuild plan is checked for existence only |
| Shareable paired cases received a separate sanitization review | Pair schema conditional requires approved review metadata | Metadata is not content inspection; re-identification risk remains contextual |
| Evaluation cases are isolated from training | Required dataset role and lineage group; the validator and negative tests reject cross-role overlap | External training pipelines must honor the recorded split |
| Historical replay is side-effect-free and version-aware | Replay context requires a legacy config reference and verified side-effect isolation | Capturing every hidden state variable is often impossible |
| Skill archives are reproducible from source | Deterministic packager enumerating git-tracked files only, byte comparison in CI, SHA-256 manifest, missing-tracked-file and untracked-file tests | Reproducibility does not by itself prove source trust or semantic correctness |
| The screening corpus matched against is the corpus the manifest attests to | `parties.jsonl` SHA-256 recorded at refresh, verified at load, refused on mismatch or absence, echoed in the `run.start` audit entry; tamper test | An attacker with write access to both the corpus and the manifest can still forge agreement; anchor the manifest externally for that threat |
| Release artifacts came from this repository workflow | GitHub artifact attestation in the tag workflow | Consumers must actually verify the attestation and repository identity |
| Test suites never run with a write-capable release token | `release.yml` grants nothing at workflow level, runs the suites in a read-only job, gives write permissions only to the release job that depends on it, and every checkout sets `persist-credentials: false`; a test asserts each of these | The release job still holds `contents: write` while it builds archives from the same tree |
| The enforcement layer cannot change without designated review | CODEOWNERS covers workflows, manifests, schemas, the validator and its wrapper, the eval runner, and `tests/`; a test asserts coverage and a single owner | CODEOWNERS is advisory unless branch protection requires code-owner review |
| Eval cases are structurally valid and their machine-checkable parts are explicit | `tools/run_evals.py` (no third-party dependency) validates the spec against `SKILL.md`, prints every case, and runs only the `machine_checks` a case declares; tests cover the spec, dry mode, and check mode | Prose expectations are graded by a person or an LLM, not by the runner; passing machine checks are necessary, never sufficient |
| The export-compliance deterministic core is tested on Python 3.11–3.14 | 379 unit/adversarial tests, hash-seed rerun, end-to-end fixture screen, cross-run disposition comparison | Fixture coverage is not legal certification or proof against all name variants |
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
