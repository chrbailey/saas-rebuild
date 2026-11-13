# Autopilot run sheet: HubSpot

**Status: partly verified.** One live run on a Free-plan account, signed in
as Super Admin, on 2026-11-12, confirmed the role, navigation, list-page
counts, audit log, and billing overview paths below. Exports, paid-tier
screens, and non-admin accounts are still unverified. HubSpot renames and
moves menus often: confirm each path on screen, and when the screen
disagrees, follow the screen and note the difference in `action_log`.

## Confirmed on the live run

- **Two sites, not one.** Login lands on `app.hubspot.com`, then the account
  opens on a regional host such as `app-na2.hubspot.com`. The browser
  extension needs permission for both, or the first read after choosing the
  account is refused.
- **Navigation.** A left sidebar shows pinned items; everything else is under
  More, in groups (CRM, Marketing, Content, Sales, Revenue, Service, Data
  Management, Agents, Automation, Reporting, Development). Each group opens a
  second panel on hover, and long panels scroll.
- **Locked items carry an upward-arrow icon** and link to a pricing page.
  They sit below a divider in each group, so used-versus-locked can be read
  without opening anything.
- **Counts are in the list-page footer** ("116 contacts"), next to the Export
  button. Board views show a count per stage instead.
- **The audit log exists on the Free plan** (Settings, Account Management,
  Audit Log), with All Logs, Login History and Security Activity tabs, a
  365-day window, and an Export report button. Integration installs appear
  there with dates.
- **Sample records.** A new account contains a deal and a contact the vendor
  labels "(Sample ...)". Exclude them from counts.
- **First-visit dialogs.** Dashboards opens a welcome dialog. Leave it alone
  and read the page another way; dismissing it changes account state.

Follow `autopilot.md` for the run itself. This sheet only says where to look.

## Never click

Send, Schedule, Enroll, Publish, Import, Delete, Merge, Turn on / Turn off,
Connect app, Upgrade, Buy, Add seats, Cancel subscription. If a finding needs
one of these, park it in `needs_you`.

## Role

- Profile menu (account name, top corner) for the account name and the hub
  id, which also appears in the address bar.
- Settings (gear icon), then Users & Teams. If this page opens and lists all
  users, record the account's own permission set and whether it is marked
  Super Admin. If it does not open, the account is not an admin.
- A seat labelled View-Only, or record pages with no Edit or Create buttons,
  indicates `view-only`.

## What is being paid for (admin with billing access only)

- Settings, then Account & Billing: products, tiers, and seat counts. This is
  the "offered" side of used-versus-paid. Record tiers and seat counts as
  `structure` evidence; do not record payment details.
- The usage and limits view in the same area lists counts against plan
  limits (for example contacts, workflows, lists, custom properties,
  reports). Each row is a ready-made usage signal.
- If these pages are not reachable, add "ask whoever pays the bill for the
  current plan and seat count" to `needs_you`.

## Start the slow exports first

Exports are prepared in the background and delivered by notification or
email, so start them before the walk. Use the routes in the recipe:

- each CRM object's list page (Contacts, Companies, Deals, Tickets, custom
  objects): Export, all properties, with associations where offered;
- Automation, Workflows: the workflow list export;
- Settings, Account Management, Audit Log: Export report, for each of its
  three tabs;
- reports and dashboards the account owns.

HubSpot has no single whole-account export, and the recipe notes a daily
export cap. Record every data class that has no export route as a
preservation gap rather than leaving it out.

## Map

Read the main navigation exactly as shown and enumerate every group and item
before opening any of them. Expect groups along the lines of CRM, Marketing,
Content, Sales, Commerce, Service, Automation, Reporting, and Data
Management, plus Settings. Items showing a lock or an upgrade prompt are
features the plan does not include: record them as nav labels with a note,
not as unused features.

## Where the usage signals are

| Area | What to read | Signal |
|---|---|---|
| Object list pages | Record total; sort by create date and by last activity date | Count, oldest, newest, last real activity |
| Deals board | Deals per stage; pipelines that exist with no deals | Used versus configured-only pipelines |
| Workflows list | On/off, enrolled totals, last modified, created by | Live versus dormant automation |
| Sequences and templates | Enrollment or send totals, last used | Use by the sales team |
| Marketing email | Sent dates and send counts | Cadence of real sending |
| Forms | Submission count and last submission | Live versus abandoned forms |
| Lists or segments | Size, last updated, where used | Dead lists |
| Reports and dashboards | Owner, last viewed or updated where shown | Reports nobody opens |
| Settings, Properties | Custom properties, where each is used, fill rate where shown | Custom fields nobody fills |
| Settings, Integrations, Connected Apps | Installed apps and install dates | Integrations to preserve or question |
| Settings, Users & Teams | Last active per user (admin only) | Paid seats nobody uses |

Totals and dates read on screen are `runtime` evidence. Record them on the
`transactional` plane (audit-log rows on `telemetry`, installed apps on
`integration-inventory`) with a structured `measure`, and name the screen in
`source`: the rules read counts only from a measure on a runtime plane, never
from the claim text. A total with no date is all-time for counts and silent on
recency: an object with 4,000 records and nothing created in two years is a
different finding from one with 40 records created last week, so always
capture both.

## Standard and view-only accounts in HubSpot

Most of the table above still works for a non-admin, limited to what the
role's permissions show ("owned only", "team only", or "everything"). Record
which of those applies, because it bounds every count. Use the "My" saved
views (my contacts, my deals, my tasks) and the activity timeline on records
the user owns as the role's history.

## Free test accounts

A free account proves the run works end to end. It has almost no history, so
nearly every feature will correctly come back "not yet known". The headline
number only means something on an account with real use.
