# On-Premise Deployment

Standing this up inside a company's own network, and replacing a screening SaaS
without losing the control while you do it.

## Why on-premise is the default here

Counterparty lists are among the most sensitive data a company holds — the
customer master, in effect. Sending it to a screening vendor is a decision with
contractual and sometimes regulatory weight. `xscreen` is standard-library
Python with no network calls outside `refresh`, and a local model backend, so
the whole pipeline can run inside the boundary.

## Install

Requirements: Python 3.11 or later. Nothing else.

```
cp -r skills/export-compliance/tools/xscreen /opt/xscreen/
cd /opt/xscreen/..
python3 -m xscreen.cli selftest              # prove the engine behaves as documented
python3 -m xscreen.cli --home /var/lib/xscreen refresh
python3 -m xscreen.cli --home /var/lib/xscreen status
```

Run `selftest` on every install and after every upgrade. It is the evidence
that the engine on *this* machine matches the documented behaviour, and it
takes two seconds.

Prose in these documents writes commands as `xscreen refresh` for readability.
The actual invocation is `python3 -m xscreen.cli --home <dir> refresh`. If you
want the short form, drop a two-line wrapper on the path:

```bash
printf '#!/usr/bin/env bash\nexec python3 -m xscreen.cli --home "${XSCREEN_HOME:-/var/lib/xscreen}" "$@"\n' \
  > /usr/local/bin/xscreen && chmod +x /usr/local/bin/xscreen
```

### Restricted egress

Many corporate networks and CI sandboxes block `.gov` hosts. That is a policy
finding to report, not something to route around. Two supported paths:

- Allowlist `data.trade.gov`, `sanctionslistservice.ofac.treas.gov`,
  `www.treasury.gov`, `www.bis.doc.gov` and `media.bis.gov` for the screening
  host.
- Or download on a permitted machine, drop the files into `lists/`, and run
  `refresh --offline`. This still produces a full manifest with SHA-256 hashes
  and row counts, so provenance is intact.

If a TLS-inspecting proxy is in the path, point `XSCREEN_CA_BUNDLE` at its CA
bundle. Never disable verification — a man-in-the-middled sanctions list is a
worse failure than no sanctions list, because it fails silently.

## Model backends

| Environment variable | Purpose |
|---|---|
| `XSCREEN_BACKEND` | Adjudicator: `anthropic:<model>`, `openai:<model>`, `offline` |
| `XSCREEN_CRITIC_BACKEND` | Critic. **Use a different model family** |
| `XSCREEN_LLM_BASE_URL` | OpenAI-compatible endpoint (vLLM, Ollama, llama.cpp, hosted) |
| `XSCREEN_LLM_MODEL` | Model name at that endpoint |
| `XSCREEN_LLM_API_KEY` | Bearer token; anything for a local server |
| `ANTHROPIC_API_KEY` | For the Anthropic backend |
| `XSCREEN_ACTOR` | Recorded in every audit entry. Set it per operator |
| `XSCREEN_CA_BUNDLE` | CA bundle for TLS-inspecting proxies |

Fully air-gapped: run two different local models, one per role. Reduced
adjudication quality is a real cost, but every guardrail still holds and the
deterministic layer — which is the part that cannot miss a hit — is unaffected.

No backend at all: the pipeline completes and routes every candidate to a
human. Slower, not wrong.

## Operating cadence

| Activity | Frequency | Command |
|---|---|---|
| Refresh lists | Daily, or before any screening run | `refresh` |
| Screen the book of business | On every list change | `screen book.csv` |
| Screen a transaction | At order entry and before shipment | `screen txn.csv` |
| Verify the audit chain | Weekly | `audit verify` |
| Publish the head hash | Daily, to write-once storage | `audit head` |
| Attest the country policy file | Quarterly, and on any FR action | `policy verify --by "Name"` |
| Confirm corpus coverage | After any narrow refresh | `status` (screening refuses an incomplete corpus outright; `--allow-stale` does not override it) |

Screening at onboarding only is the most common design mistake. Destination and
end use change per shipment even when the customer does not, and a party you
cleared in March can be designated in April.

### Wiring the cadence

Linux/macOS, refresh and re-screen every weekday morning, keeping the previous
run for comparison:

```cron
# m  h  dom mon dow  command
  15 6  *   *   1-5  /usr/bin/python3 -m xscreen.cli --home /var/lib/xscreen refresh >> /var/log/xscreen.log 2>&1
  30 6  *   *   1-5  /opt/xscreen/rescreen.sh >> /var/log/xscreen.log 2>&1
```

```bash
#!/usr/bin/env bash
# /opt/xscreen/rescreen.sh -- re-screen the book and report what changed.
set -uo pipefail
HOME_DIR=/var/lib/xscreen
BOOK=/var/lib/xscreen/book-of-business.csv
export XSCREEN_ACTOR="scheduled"

PREV=$(ls -1d "$HOME_DIR"/runs/*/ 2>/dev/null | tail -1)
python3 -m xscreen.cli --home "$HOME_DIR" screen "$BOOK"
code=$?
[ "$code" -eq 1 ] && { echo "screening failed to run"; exit 1; }

NEW=$(ls -1d "$HOME_DIR"/runs/*/ | tail -1)
if [ -n "$PREV" ] && [ "$PREV" != "$NEW" ]; then
  python3 -m xscreen.cli --home "$HOME_DIR" diff \
    "$PREV/dispositions.csv" "$NEW/dispositions.csv" --out "$NEW/CHANGES.md"
  # Exit 3 from diff means a party that was clear is not any more.
  [ $? -eq 3 ] && echo "NEW HITS -- see $NEW/CHANGES.md"
fi
python3 -m xscreen.cli --home "$HOME_DIR" cases --out "$HOME_DIR/OPEN_CASES.md"
python3 -m xscreen.cli --home "$HOME_DIR" audit head >> "$HOME_DIR/audit/head-log.jsonl"
```

Windows, the same shape via Task Scheduler:

```powershell
$py = "C:\Program Files\Python312\python.exe"
$home = "C:\ProgramData\xscreen"
schtasks /Create /TN "xscreen refresh" /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST 06:15 `
  /TR "`"$py`" -m xscreen.cli --home `"$home`" refresh"
schtasks /Create /TN "xscreen rescreen" /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST 06:30 `
  /TR "`"$py`" -m xscreen.cli --home `"$home`" screen `"$home\book-of-business.csv`""
```

Nothing in the package is POSIX-specific; the audit lock uses `msvcrt` on
Windows and `fcntl` elsewhere. Substitute Windows paths for the `/opt` and
`/var/lib` conventions used above.

### Reading the diff

`xscreen diff before/dispositions.csv after/dispositions.csv` categorizes every
reference and exits `3` when anything moved from clear to not-clear. The
category that matters is **New hits** — but a new hit is not necessarily a new
designation. It can equally mean the party's name or address changed in your
system, that the alternate-names file loaded this time and not last time, or
that a threshold moved. Compare the two runs' list manifest digests before
concluding which.

`xscreen cases` rolls every still-open case across all runs into one worklist,
newest screening per reference. It answers "what is still outstanding", which
no single run report can.

## The country policy file

`tools/xscreen/policy/destinations.json` is **operator-maintained and ships
unattested**. It is not law. Every rule derived from it carries its `as_of`
date and a warning until an operator attests it with `policy verify`.

Attesting means someone checked the entries against 15 CFR Part 740 Supp. 1,
Part 746, 22 CFR 126.1 and the current OFAC program pages, and put their name
on it. Re-attest quarterly and whenever a Federal Register action moves a
country. An unattested policy file produces screening output that says so, in
the report, where an auditor will see it.

## Roles and separation of duties

At minimum three, and the last two must not be the same person:

- **Operator** — runs refresh and screen, maintains the party file.
- **Reviewer** — adjudicates non-CLEAR dispositions, obtains ownership
  information and end-user statements.
- **Approver** — signs off on releasing or blocking a transaction.

Set `XSCREEN_ACTOR` per person so the audit log attributes actions. The audit
chain records who ran what; the human decision record (see
`templates/license-determination-worksheet.md`) records who decided.

## Audit and retention

The log is append-only and hash-chained. `audit verify` detects modified
payloads, deleted entries, reordering, and — via the `HEAD` marker written
beside it — truncation of the most recent entries, which forward verification
alone cannot see. Make `HEAD` root-owned in a real deployment: an attacker who
has to edit two files in agreement is doing something far more deliberate than
running `truncate`. It is tamper-*evident*, not
tamper-proof — a person with write access can recompute the whole chain. What
makes it real evidence is publishing the daily head hash somewhere that person
cannot rewrite: write-once object storage, a ticketing system, a signed email
to the compliance officer, a commit in a repository they do not control.

Retain five years (EAR 762.6; OFAC 501.601).

### Backup and restore

The three things that must survive together, because none is useful alone:

| Path | Why it is needed |
|---|---|
| `audit/screening-audit.jsonl` | The record itself. Losing any line breaks the chain. |
| `lists/*.raw` + `lists/manifest.json` | A disposition cannot be reconstructed without the list snapshot it was computed against. The manifest hash is the join. |
| `runs/*/` | The reports and per-case results an auditor will actually read. |

```bash
tar -czf "xscreen-$(date -u +%Y%m%d).tar.gz" \
    -C /var/lib/xscreen audit lists runs
```

Restore is a plain extract, followed immediately by `audit verify` — if the
chain does not verify after a restore, the backup is incomplete or the archive
is truncated, and that must be resolved before the log is appended to again.
Appending to a broken chain buries the break under new entries.

Two operational notes:

- **`lists/*.raw` dominates the size** and is the part people are tempted to
  skip. Skipping it means a five-year-old disposition can no longer be
  explained, which is the one thing the retention rule exists to make possible.
- **Verify a restore somewhere else once**, before you need it. A backup you
  have never extracted is a hypothesis.

If the audit log is truncated or half-written after a crash, `audit verify`
reports the break with the sequence number where it occurred. Do not repair it
by editing — that is indistinguishable from tampering. Start a new log file,
note the discontinuity and its cause in writing, and retain the damaged file
alongside it.

## Replacing a screening SaaS

The sequence, borrowed from `saas-rebuild`'s strangler-fig approach.

**1. Inventory what the incumbent actually does.** Usually: list matching, case
management, an audit trail, scheduled re-screening, an attestation that
somebody else maintains the lists, and often ERP/e-commerce integrations. This
tool replaces the first four. Be explicit with the operator about the last two.

**2. Parallel run.** Screen the same book through both systems and diff the
dispositions. Do not assume either is right. Every discrepancy is a finding:

- Hit here, clear there → check whether the incumbent's threshold is higher, or
  whether it screens fewer lists or omits alternate names.
- Clear here, hit there → the highest-value finding. Investigate every one. It
  is either a real recall gap to fix or a false positive to characterize.
- Different disposition on the same hit → usually a legal-effect difference
  (Non-SDN or UVL), which is worth resolving on the merits.

**3. Tune only on that evidence**, and prefer fixing normalization over raising
thresholds. Record every change with its justification.

**4. Cut over when the diff is understood, not when it is empty.** It will not
be empty. Two tools draw the fuzzy-match line differently, and pretending
otherwise means you cut over on a number rather than on understanding.

**5. Keep the old system read-only for the retention period**, or export its
history first. Screening records are the thing regulators ask for.

### What you are not replacing

Be honest about this with the operator. A commercial provider supplies list
maintenance as a *service* with an SLA, plus somebody to point at when the
list was stale. Running this yourself moves that responsibility onto the
operator. The staleness check, the degraded-refresh flag and the manifest exist
to make that responsibility visible rather than implicit, but they do not
discharge it.

## Integrating with a shipping gate

Exit codes are designed for it: `0` clean, `1` infrastructure or usage error,
`2` cases need human review, `3` at least one BLOCKED.

```
python3 -m xscreen.cli --home /var/lib/xscreen screen "$ORDER_CSV" --out "$OUT"
case $? in
  0) echo "cleared" ;;
  2) echo "hold: human review required"; exit 1 ;;
  3) echo "blocked"; exit 1 ;;
  *) echo "screening failed to run"; exit 1 ;;   # never treat as cleared
esac
```

The last branch matters most. A screening tool that cannot run must block the
shipment, not wave it through. Every failure path in this system is built that
way; make sure your integration is too.
