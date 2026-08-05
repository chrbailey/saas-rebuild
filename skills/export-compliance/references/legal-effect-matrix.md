# Legal Effect Matrix

What a hit on each list actually prohibits. This is a working reference for
building and reading screening output — **not legal advice**, and not a
substitute for the primary publication. Citations are given so the primary can
be found; read it before acting on anything here.

The single most common and most expensive screening error is treating every
list as if it meant the same thing. It does not. Three of these lists prohibit
dealing outright, three impose a licence requirement scoped to specific items,
and one is a diligence trigger that many programs wrongly auto-block.

## The matrix

| List | Agency | Effect of a confirmed hit | Authority |
|---|---|---|---|
| **SDN** | Treasury/OFAC | Property blocked; U.S. persons generally prohibited from dealing. Strict liability. | 31 CFR Ch. V |
| **Non-SDN Consolidated** (SSI, FSE, CAPTA, NS-PLC, NS-MBS, NS-CMIC) | Treasury/OFAC | Program-specific and usually **narrower than blocking**. Read the program tag and the governing directive. | 31 CFR Ch. V; directives |
| **DPL** (Denied Persons) | Commerce/BIS | Export privileges denied by order. No participation in any EAR transaction for the order's term. No licence exception available. | 15 CFR Part 764 |
| **Entity List** | Commerce/BIS | Licence required **for the items specified in that entry**, with a stated review policy (often presumption of denial). Licence exceptions limited per the entry. | 15 CFR Part 744, Supp. 4 |
| **UVL** (Unverified) | Commerce/BIS | No licence exceptions; UVL statement required from the party before an otherwise-NLR shipment. **Not a prohibition on dealing.** | 15 CFR 744.15, Supp. 6 |
| **MEU** (Military End User) | Commerce/BIS | Licence required for Supplement No. 2 to Part 744 items; presumption of denial. | 15 CFR 744.21, Supp. 7 |
| **DDTC Debarred** | State/DDTC | Prohibited from participating directly or indirectly in ITAR-controlled exports. | 22 CFR 127.7 |
| **ISN nonproliferation** | State/ISN | Measures vary by the statute and the determination. No single rule. | Various; read the FR notice |

## The errors this table exists to prevent

**Treating a Non-SDN hit as blocking.** SSI parties are subject to specific
debt- and equity-maturity restrictions, not a prohibition on all dealing. Over-
blocking here refuses lawful business *and* hides the restriction that actually
applies, so it fails in both directions at once.

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
  impose their own filing deadlines. A blocking report is generally due within
  10 business days. Screening evidence is not the report.

Keep the screening evidence, the adjudication, the human decision and the list
snapshot hash together. A disposition without the snapshot it was computed
against cannot be reconstructed, and an auditor will ask.
