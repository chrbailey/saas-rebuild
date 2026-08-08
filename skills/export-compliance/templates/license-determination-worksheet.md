# Export Determination Worksheet — {REF} / {COUNTERPARTY}

The human half of the record. `xscreen` produces the machine half; this is
where a person decides and signs. Keep both together for five years (EAR 762.6;
OFAC 501.601).

**Not legal advice.** Complete on advice of counsel where the answer is not
plain.

---

## 1. Transaction

| Field | Value |
|---|---|
| Internal reference | {REF} |
| Date of determination | {DATE} |
| Counterparty | {COUNTERPARTY} |
| Role (customer / end user / consignee / intermediary / bank) | {ROLE} |
| Ultimate end user (if different) | {END_USER} |
| Ultimate destination | {DESTINATION} |
| Item | {ITEM} |
| Stated end use, in the customer's words | {END_USE} |
| Value | {VALUE} |

## 2. Screening evidence

| Field | Value |
|---|---|
| Screening run | {RUN_ID} |
| List snapshot digest | {MANIFEST_DIGEST} |
| List age at screening | {LIST_AGE} days |
| Stale override used | {STALE_OVERRIDE} |
| Engine disposition | {DISPOSITION} |
| Adjudication model | {ADJ_MODEL} |
| Critic model | {CRITIC_MODEL} |
| Critic route | {CRITIC_ROUTE} |
| Audit entries | {AUDIT_RANGE}, head {AUDIT_HEAD} |

### Candidate matches

| List | Matched name | Band | Score | Adjudication | Human conclusion |
|---|---|---|---|---|---|
| | | | | | |

For each row, state the evidence the human conclusion rests on. "Different
address" is not sufficient on its own — see
`references/adjudication-playbook.md`.

## 3. The five EAR questions

Answer all five. A clean party screen answers one of them.

| # | Question | Answer | Basis |
|---|---|---|---|
| 1 | What is the item, and what is its classification? | {ECCN} | {CLASS_BASIS} |
| 2 | Where is it going (ultimate destination)? | {DESTINATION} | |
| 3 | Who will receive and use it? | {END_USER} | |
| 4 | What will it be used for? | {END_USE} | |
| 5 | What else is known about the transaction? | | |

Classification basis: self-classification / CCATS ruling / manufacturer
statement / counsel opinion. Record which — "we think it's EAR99" is not a
basis.

## 4. Obligations raised by the run

Every rule flag needs a disposition. An open obligation is not a clear.

| Rule | Obligation | Status | Evidence / document |
|---|---|---|---|
| | | open / satisfied / n/a | |

Recurring ones worth checking explicitly:

- [ ] **OFAC 50 Percent Rule.** Beneficial ownership obtained where an SDN hit
      involved an entity. Remember ownership aggregates across multiple blocked
      persons and applies indirectly through intermediate companies.
- [ ] **UVL statement** obtained, where a UVL party is involved.
- [ ] **Entity List entry read**, item scope confirmed, footnote designations
      checked for Foreign Direct Product Rule application.
- [ ] **Non-SDN program directive** read; the specific restriction identified.
- [ ] **Denial order dates** checked against the transaction date.
- [ ] **End user identified and separately screened**, where this counterparty
      is an intermediary.
- [ ] **Know Your Customer red flags** resolved and the resolution documented
      (15 CFR Part 732, Supp. 3). Inquired, and recorded the answer.
- [ ] **744.21 military end-user analysis**, independent of MEU List presence.
- [ ] **Deemed export** considered, if controlled technology will be released
      to foreign nationals.

## 5. Determination

**Outcome:** ☐ Proceed, no licence required ☐ Proceed under licence exception
☐ Licence application required ☐ Reject / block ☐ Hold pending information

**Authority relied on:** {AUTHORITY}

**Reasoning:**

{REASONING}

**If blocked or rejected under an OFAC program**, note the reporting deadline.
A blocking report is generally due within 10 business days (31 CFR 501.603);
rejected transactions have their own requirement (501.604). Screening evidence
is not the report.

| Report | Due | Filed | Reference |
|---|---|---|---|
| | | | |

## 6. Sign-off

Reviewer and approver must be different people.

| Role | Name | Date | Signature |
|---|---|---|---|
| Prepared by | | | |
| Reviewed by | | | |
| Approved by | | | |

## 7. Re-screening

| Field | Value |
|---|---|
| Re-screen on list change | yes / no |
| Next scheduled re-screen | {NEXT_DATE} |
| Conditions requiring immediate re-screen | ownership change, address change, new consignee, new end use |

A determination is valid for the facts recorded above. Change any of them and
it lapses.
