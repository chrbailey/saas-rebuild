# Jev contract spike — 2026-09-22

This is bounded M1 evidence, not a production-readiness claim.

One shadow-mode call sent the synthetic/public `customer-search` example and
all eight Feature Perception questions to the documented System One endpoint.
The boundary ticket, minimizer, one-call limit, 2,000-input-token limit, and
$5 guard were active before network I/O.

| Observation | Result |
|---|---|
| HTTP contract | Accepted |
| Model returned | `jev-1.13.0` |
| Questions parsed | F1–F8 (Choice and Noul) |
| Provider input tokens | 925 |
| Provider output tokens | 301 |
| Client-observed latency | 163 ms |
| Request id header | Not returned |
| Shadow effects | `none` only |
| Replay | Cache hit; zero additional calls/tokens |
| Artifact validation after replay | Passed |

TypeSafe's public price at the time of the spike was
[$0.042 per million input tokens with output free](https://typesafe.ai/blog/introducing-system-one-models-and-jev),
so the measured input cost was $0.00003885. The committed response fixture
contains only synthetic model output and no credential or raw call log.

This spike does not establish the 500-state, three-repeat agreement gate,
calibration quality, reviewer-time savings, or performance on a real
engagement. Until those gates pass, high-authority outputs remain shadowed or
demoted to prioritization, and the deterministic rules remain authoritative.
