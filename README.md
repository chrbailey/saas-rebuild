# saas-rebuild

Two Claude Code skills for teams pulling software back in-house.

- **`saas-rebuild`** — tear down a SaaS application you administer and plan its
  replacement as a Claude skill.
- **`export-compliance`** — run U.S. export-control restricted-party screening
  on premise against the official government lists, replacing a screening SaaS
  outright. See [below](#export-compliance--restricted-party-screening).

Both are built to the same standard: every rule the prose states is enforced
by a schema, a test, or code — never by trust. Verdicts require typed,
cited evidence or they revert; the packaged zips must be byte-identical to
source or CI fails; the CI suite parses the docs and set-compares their
enumerations against the schemas so prose and contract cannot drift; a
version bump that passes the suite releases itself; screening decisions
carry a hash-chained audit trail and rerun deterministically under changed
hash seeds. The methodology states its own failure modes — replay
preconditions, evidence-window limits, articulation-point blind spots —
because an analysis that hides its limits isn't evidence.

---

## saas-rebuild — teardown and rebuild planning

A Claude Code skill that helps you **tear down a SaaS application you
administer and plan its replacement as a Claude skill**.

Most teams use a fraction of the software they pay for. This skill runs a
phased pipeline to find out which fraction, and what a leaner replacement
looks like:

1. **Scope and pre-flight** — which app, which modules, who uses it — plus
   the day-one clock-starters: snapshot volatile logs before retention
   windows lapse, request contracts from finance, note the post-termination
   data-retrieval window as the project's hardest deadline.
2. **Feature inventory** — a breadth-first browser walk of every screen,
   form, report, and setting (via browser automation on *your* authenticated
   session; the skill never handles credentials), plus a technical pass over
   five data planes through the platform's own APIs: configuration census
   (the delta from vanilla is the requirements list you paid for),
   transactional archaeology, master-data fill rates, setup census, and
   static analysis of customization code.
3. **Usage evidence** — record counts, telemetry, exports, contracts, and
   structured user interviews. Where the audit log qualifies, process mining
   turns "how work really flows" into counted evidence: variants,
   configured-vs-lived conformance, bottleneck waits.
4. **Used-vs-unused verdicts** — every KEEP / SIMPLIFY / DROP / DEFER
   verdict carries typed evidence citations (which plane, what claim, what
   source, per the JSON schema); a verdict without a citation reverts to
   DEFER. A feature counts as "used" only when structural and runtime
   evidence join. A dependency graph assembled from the planes derives the
   risk register and re-challenges KEEPs nothing depends on.
5. **Extraction map and preservation export** — the best route to get each
   kept entity's data out (API/connector → built-in export → report CSV →
   scrape as last resort), and a full-tenant preservation export that runs
   regardless of verdicts: every entity, attachments, activity history, the
   audit logs themselves, and configuration as restorable artifacts —
   verdicts decide what gets rebuilt, never what gets saved.
6. **Rebuild plan** — milestones derived from the dependency graph
   (strangler-fig, never big-bang), validated by replaying real historical
   transactions against the system of record, with the replay preconditions
   stated and an expected-divergence register for intended improvements.

**Day-one extraction knowledge.** Nearly every SaaS contract lets the
customer export their own data; almost nobody has ever tried. The skill
ships an extraction-recipe corpus for the 100 most widely-adopted B2B SaaS
apps (`skills/saas-rebuild/corpus/`): per app, the documented export
rights and post-termination retrieval window, the extraction routes in
preference order with role/SKU gates and gotchas, and the preservation
answers (attachments, audit log, configuration artifacts) — every claim
cited to vendor documentation with retrieval dates. Name your app at
login and Phase 0 loads its recipe. Recipes start `doc-derived-unverified`
and are promoted to `tenant-verified` only when a real teardown confirms
them — corrections flow back as PRs.

The teardown is also a labeling process, and the skill harvests the labels:
every phase appends supervised (input, output) pairs to `pairs.jsonl` —
screen-to-schema, evidence-to-verdict, transaction-to-output,
evidence-to-design. The replay corpus makes the rebuild a distillation of
the legacy system against ground truth, and doubles as the replacement's
permanent regression suite. Each pair carries a sanitization tier and a
label authority; raw tenant data never leaves the output directory.

No live tenant? A document-based mode runs the same pipeline against
engagement archives — change tickets, FRDs, training manuals,
rescue-project findings.

Outputs land in `~/Dev/teardowns/<app-slug>/` with a resumable state file, so
a teardown can span multiple sessions (and wait for interview answers).

## Install

**As a plugin (recommended):**

```
/plugin marketplace add chrbailey/saas-rebuild
/plugin install saas-rebuild
```

**Manual:** copy `skills/saas-rebuild/` and/or `skills/export-compliance/`
into `~/.claude/skills/`.

**Project-level:** copy the same folder(s) into your repo's
`.claude/skills/` — everyone who clones the repo gets them.

## Use

Say things like:

- "Tear down our CRM"
- "What do we actually use in [app]?"
- "Replace [app] with a skill"

A browser-automation MCP (e.g. Claude in Chrome) covers the UI-walk phase;
the deeper extraction phase uses the platform's own metadata API or SQL
where you have it, and you'll need admin access to the app you're
analyzing. No live tenant? The document-based mode runs the same pipeline
against engagement archives instead.

## Share your teardown — let's replace SaaS collectively

Every teardown produces the same artifacts: a feature map with KEEP /
SIMPLIFY / DROP / DEFER verdicts, each carrying typed evidence citations
(which data plane, what claim, what source), plus a `pairs.jsonl` training
corpus in three sanitization tiers. Those maps are far more valuable
shared than siloed:

- **The used-fraction repeats.** If your team uses 20% of your CRM, odds are
  the next team uses a similar 20%. One shared teardown is a head start for
  everyone on the same app or category.
- **Others uncover what you missed.** A second teardown of the same app finds
  the modules, workflows, and workarounds your walk skipped — and gaps in
  this pipeline itself (a phase that needs a step, a signal the schema
  doesn't capture).
- **Convergent verdicts become community skills.** When several teardowns of
  an app category agree on the KEEP set, that's a spec: the community can
  build and maintain one replacement skill instead of each team rebuilding
  alone.

**How to post results:** open a
[Teardown Report issue](../../issues/new?template=teardown-report.yml) with
the app (or just its category, if you'd rather not name it), feature counts
by verdict, your top "why unused" reasons, and anything the pipeline missed.
If you captured pairs, say how many landed in the `sanitized-shareable` and
`synthetic` tiers — convergent pair corpora are how a community replacement
skill gets its regression suite. PRs improving the phases, templates, or
schema are very welcome.

**Sanitize before you share.** Your teardown output contains your business
data — the report you post must not. No record contents, no exports, no
customer or employee names, no screenshots with real data, no internal URLs.
Share the *structure* (feature names, verdicts, why-categories, rough record
counts as ranges). The pairs schema enforces this as a field:
`raw-local-only` pairs never leave your output dir; only
`sanitized-shareable` and `synthetic` tiers travel. If in doubt, leave it
out — a verdict table with no numbers is still useful.

## Responsible use

This skill is for analyzing **your own tenant** of software you legitimately
administer, for migration planning. It will not probe other tenants or other
users' private data, and it prefers official exports/APIs over scraping.
Before any bulk extraction the skill walks you through a vendor-agreement
checklist — export rights, API terms, anti-scraping clauses, and the
post-termination data-retrieval window — and says when to involve counsel.

---

# export-compliance — restricted party screening

Screen counterparties against the official U.S. denied and restricted party
lists, decide what a hit means for a specific shipment, and leave a record that
survives an audit five years later. Runs entirely on your own hardware.

Built for a small business that needs a defensible answer today, a legal team
that needs the basis for it, and a company pulling this function back in-house
from a screening SaaS.

## What it screens against

All official, all free, all U.S. government:

| Source | Agency |
|---|---|
| Consolidated Screening List (CSL) | ITA (aggregate) |
| Specially Designated Nationals (SDN) + alternate names + addresses | Treasury/OFAC |
| Non-SDN Consolidated (SSI, FSE, CAPTA, NS-PLC, NS-MBS, NS-CMIC) | Treasury/OFAC |
| Denied Persons List (DPL) | Commerce/BIS |
| Entity List, Unverified List, Military End User List | Commerce/BIS |
| ITAR Debarred Parties | State/DDTC |
| Nonproliferation sanctions | State/ISN |

CSL is the operational source because it is one clean file covering every
agency. It is **not** the legal source of record — the tool says so on every
hit, and points at the primary publication.

## The design in one table

**Extraction and matching are deterministic. Analysis is not. Nothing is
cleared by a model alone.**

| Stage | Who does it |
|---|---|
| Fetch and parse the lists | Code — provenance is a SHA-256, not a recollection |
| Name matching and scoring | Code — same input, same result, in 2031 |
| Legal effect of a hit | Code — an SDN hit's consequence is not a judgement call |
| Is this the same party | Model — needs context a string metric cannot read |
| Was that judgement sound | Independent critic model, ideally a different family |
| What to do about it | Human — strict liability, a person signs |

A case with any candidate above the review floor can never end as CLEAR. A
model verdict of "different party" against an exact name match does not clear
it. A backend timeout is never a pass. These are enforced in code, not in a
prompt, and the test suite is largely an attempt to break them.

## Try it

Zero dependencies — standard-library Python 3.11+, no network calls outside
`refresh`, so it installs and runs inside a closed network.

```bash
cd skills/export-compliance/tools
python3 -m xscreen.cli selftest                      # 274 tests, ~3 seconds
python3 -m xscreen.cli --home ~/xs refresh           # pull the official lists
python3 -m xscreen.cli --home ~/xs screen parties.csv
python3 -m xscreen.cli --home ~/xs explain "Acme Trading Ltd"
python3 -m xscreen.cli --home ~/xs audit verify
```

Exit codes make it a shipping gate: `0` clean, `1` failed to run, `2` human
review needed, `3` blocked. A screening tool that cannot run must block the
shipment, not wave it through.

Roughly 21 ms per counterparty against a 25,000-name index — a 10,000-party
book of business screens in about 3.5 minutes on one core.

## What it will not do

The report says all of this in every run, because each is a real gap that name
screening cannot close:

- **The OFAC 50 Percent Rule.** Entities owned 50% or more, in the aggregate,
  by blocked persons are themselves blocked and appear on no list. There is no
  name to match. This needs beneficial-ownership diligence.
- **Classification.** Whether a licence is required depends on the item's ECCN.
- **End-use controls on unlisted parties.** 15 CFR 744.21 applies to military
  end users whether or not they are on the MEU List.
- **Entity List scope.** The licence requirement covers the items named in the
  entry, and footnotes can trigger a Foreign Direct Product Rule. Read it.

**Not legal advice.** It produces screening evidence and a structured analysis;
a licensing decision is made by the operator on advice of counsel.

## Responsible use

Screen your own counterparties for your own compliance obligations. The country
policy file ships **unattested** and every rule derived from it says so until an
operator checks it against the current CFR and signs. Government lists change
weekly — the tool refuses to run on a snapshot older than seven days, and
records the override when you make it run anyway.

## License

MIT
