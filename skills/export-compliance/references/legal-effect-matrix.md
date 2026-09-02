# Legal Effect Matrix

What a hit on each list actually prohibits. This is a working reference for
building and reading screening output — **not legal advice**, and not a
substitute for the primary publication. Citations are given so the primary can
be found; read it before acting on anything here.

The single most common and most expensive screening error is treating every
list as if it meant the same thing. It does not. Four prohibit dealing
outright (SDN, FSE, DPL, DDTC Debarred), two impose a licence requirement scoped to
specific items (Entity List, MEU), one is a diligence trigger that programs
routinely and wrongly auto-block (UVL), and two are program-specific with no
single rule (Non-SDN, ISN).

**Only U.S. lists are covered here.** A commercial screening service almost
certainly also screened EU, UK and UN designations. Replacing it with this
tool does not replace that coverage.

## The matrix

| List | Agency | Effect of a confirmed hit | Authority |
|---|---|---|---|
| **SDN** | Treasury/OFAC | Property blocked; U.S. persons generally prohibited from dealing. Strict liability. | 31 CFR Ch. V |
| **FSE** (Foreign Sanctions Evaders) | Treasury/OFAC | U.S. persons prohibited from **all transactions or dealings**, direct or indirect, with the listed person absent a licence. Not a blocking action — property is not frozen — but the dealing is prohibited. Published alongside the Non-SDN lists; do not read it as one. | EO 13608, sec. 1; confirm the current entry |
| **Non-SDN Consolidated** (SSI, CAPTA, NS-PLC, NS-MBS, NS-CMIC) | Treasury/OFAC | Program-specific and usually **narrower than blocking**. Read the program tag and the governing directive. | 31 CFR Ch. V; directives |
| **DPL** (Denied Persons) | Commerce/BIS | Export privileges denied by order. No participation in any EAR transaction for the order's term. No licence exception available. | 15 CFR 736.2(b)(4); Supp. 1 to Part 764; Part 766 |
| **Entity List** | Commerce/BIS | Licence required **for the items specified in that entry**, with a stated review policy (often presumption of denial). Licence exceptions limited per the entry. | 15 CFR 744.16; Supp. 4 to Part 744 |
| **UVL** (Unverified) | Commerce/BIS | No licence exceptions; UVL statement required from the party before an otherwise-NLR shipment. **Not a prohibition on dealing.** | 15 CFR 744.15, Supp. 6 |
| **MEU** (Military End User) | Commerce/BIS | Licence required, presumption of denial. **Scope varies by destination**: Supp. 2 to Part 744 items for Burma, Cambodia, China, Nicaragua and Venezuela; **all items subject to the EAR** for Russia and Belarus. | 15 CFR 744.21, Supp. 7 |
| **DDTC Debarred** | State/DDTC | Prohibited from participating directly or indirectly in ITAR-controlled exports. | 22 CFR 127.7 |
| **ISN nonproliferation** | State/ISN | Measures vary by the statute and the determination. No single rule. | Various; read the FR notice |

## The errors this table exists to prevent

**Treating a Non-SDN hit as blocking.** SSI parties are subject to specific
debt- and equity-maturity restrictions, not a prohibition on all dealing. Over-
blocking here refuses lawful business *and* hides the restriction that actually
applies, so it fails in both directions at once.

**Reading an FSE hit as a Non-SDN "narrow" restriction.** The Foreign
Sanctions Evaders List is published in OFAC's consolidated Non-SDN file, but
EO 13608 imposes a general prohibition on transactions and dealings with the
listed person — the opposite of narrow. `xscreen` raises `LIST.FSE` at
prohibitive severity whether the row arrived under the CSL's FSE source label
or as a Non-SDN row tagged FSE-IR / FSE-SY. Confirm the current entry: the
Syria leg was affected by the 2025 revocation of the Syria program, and many
FSE parties are also SDNs, in which case blocking governs.

**Auto-blocking UVL parties.** A UVL listing means BIS could not complete an
end-use check. The obligation it creates is a documented UVL statement, not a
stop. Auto-blocking is over-compliance that costs real revenue.

**Reading an Entity List hit as a blanket prohibition — or a blanket
permission.** The licence requirement attaches to the items named in the entry.
Items outside that scope may need no licence; items inside it may be near-
impossible to licence. Both errors come from not reading the entry.

**Ignoring denial-order dates.** DPL orders have effective and expiration
dates. A stale list over-flags expired orders; a fresh list evaluated against
the wrong transaction date does the same. `xscreen` compares against `--as-of`
and downgrades expired orders to informational, but the dates still have to be
right in the source data.

**Missing footnote designations.** Entity List footnotes (1, 3, 4, 5 and
successors) carry additional rules including Foreign Direct Product Rules.
These do not survive aggregation into the CSL reliably. If an Entity List hit
matters, read Supplement No. 4 itself.

## What no list can tell you

**The OFAC 50 Percent Rule.** An entity owned 50 percent or more, directly or
indirectly, in the aggregate, by one or more blocked persons is itself blocked
— and **is not listed**. There is no name to match. This is the single largest
category of blocked counterparty that name screening structurally cannot find.
It requires beneficial-ownership diligence.

Two aggregation traps inside the rule: ownership is *aggregated* across
multiple blocked persons (two blocked persons at 30% each blocks the entity),
and it is *indirect* (a blocked person owning 50% of A, which owns 50% of B,
reaches B). Neither is intuitive and both are routinely missed.

**Whether a licence is required at all.** That depends on the item's
classification, the destination, the end use and the end user together. A
clean party screen answers one of four questions.

**Unlisted military end users.** 15 CFR 744.21 applies to military end users
in listed destinations regardless of whether the party appears on the MEU List.
The list is a convenience, not the boundary of the obligation.

**The BIS Affiliates Rule.** Commerce adopted an analogous rule extending
Entity List, MEU and denial-order restrictions to entities majority-owned by
listed parties. It was suspended for one year in November 2025. A suspension is
not a repeal — verify its current status rather than relying on its absence,
because an operator standing this tool up now may be inside the snap-back
before their first quarterly policy re-attestation.

**Deemed exports.** Releasing controlled technology to a foreign national
inside the United States is an export to their home country. No shipment
occurs and no counterparty is screened, so this pipeline never sees it.

## Source-of-record discipline

The Consolidated Screening List is the right *operational* source: one clean
file, all agencies, regular updates. It is the wrong *legal* source. It is an
aggregation maintained by ITA, it can lag a Federal Register action, and it
flattens fields the primary files carry — notably OFAC alternate-name types and
Entity List licence policy.

Practical rule: screen against CSL plus the OFAC primaries for breadth, and
confirm any hit that will drive a decision against the primary publication and
the Federal Register notice. Record which you used; `xscreen` writes the source
of every candidate into the result.

## Retention

- **EAR:** 15 CFR 762.6 — five years from the date of export, reexport,
  transfer, or the relevant transaction.
- **OFAC:** 31 CFR 501.601 — five years, including records of blocked and
  rejected transactions.
- **Blocked-property and rejected-transaction reports:** 31 CFR 501.603/501.604
  impose their own filing deadlines, and they are **different obligations**.
  Blocking freezes property (501.603); rejecting refuses the transaction
  (501.604). Returning property that must be blocked is itself a prohibited
  transfer of blocked property. Both initial reports are generally due within
  10 business days.
- **Annual Report of Blocked Property:** due 30 September each year for
  property blocked as of 30 June. Easy to miss; it is not the initial report.
  Screening evidence is not either report.

Keep the screening evidence, the adjudication, the human decision and the list
snapshot hash together. A disposition without the snapshot it was computed
against cannot be reconstructed, and an auditor will ask.
