# Remediation Tracker V5

**Started:** 2026-05-06T20:38:00-04:00
**Branch:** audit-v4-remediation
**Baseline commit:** 7b27b288f71e0becf0182ec914661824e308ef9e

## Phase status

| Phase | Status | Started | Completed | Smoke tests | Commit |
|---|---|---|---|---|---|
| 0 | done | 2026-05-06 20:38 | 2026-05-06 20:40 | 52/52 | (in-flight) |
| 1 | pending | — | — | — | — |
| 2 | pending | — | — | — | — |
| 3 | pending | — | — | — | — |
| 4 | pending | — | — | — | — |
| 5 | pending | — | — | — | — |
| 6 | pending | — | — | — | — |
| 7 | pending | — | — | — | — |
| 8 | pending | — | — | — | — |
| 9 | pending | — | — | — | — |
| 10 | pending | — | — | — | — |
| 11 | pending | — | — | — | — |

## Findings tracker

(Numbering follows the remediation prompt's phase-by-phase fix list, mapping back to V4 audit Section 3 / Section 4 / Section 5 where possible.)

| # | Title | Phase | Status | Files touched | Verified | Notes |
|---|---|---|---|---|---|---|
| 1 | /shop/ipo NameError 500 | 1 | pending | — | — | V4 §3.1, §C.4 |
| 2 | No UI to approve pending shops | 1 | pending | — | — | V4 §3.2, §C.5 |
| 3 | Nation leader can self-approve own shop | 1 | pending | — | — | V4 §3.3, §C.6 |
| 4 | Helper for relational leader check | 2 | pending | — | — | new infra |
| 5 | Suspend nation demotes leader role | 2 | pending | — | — | role drift |
| 6 | Unsuspend re-promotes leader role | 2 | pending | — | — | role drift |
| 7 | WM-as-leader access to /nation/* | 2 | pending | — | — | V4 §3.4, §D |
| 8 | Standardize role-check pattern | 2 | pending | — | — | hygiene |
| 9 | Reject pending nation endpoint | 2 | pending | — | — | confirm exists |
| 10 | Unsuspend nation endpoint | 2 | pending | — | — | tied to fix 6 |
| 11 | Leadership-transfer flow | 2 | deferred-to-followup | — | — | needs design input |
| 12 | Validate user not already in nation on apply | 2 | pending | — | — | new guard |
| 13 | Hide "Open a Shop" CTA when ineligible | 3 | pending | — | — | V4 §3.6 |
| 14 | Pending-nation user shouldn't see shop CTA | 3 | pending | — | — | V4 §A.2/B.3 |
| 15 | Suspended-nation leader navbar gate | 3 | pending | — | — | V4 §E.2 |
| 16 | Approve/Reject buttons on /mint/nations | 3 | pending | — | — | V4 §3.10 |
| 17 | /nations empty-state CTA | 3 | pending | — | — | V4 §N.2 |
| 18 | Block listing creation on pending shops | 3 | pending | — | — | V4 §C.3 |
| 19 | Pending-shop banner on /shop/manage | 3 | pending | — | — | V4 §C.2 |
| 20 | /loans/apply empty state by role | 3 | pending | — | — | V4 §N.3 |
| 21 | /send max="0" poisoning | 4 | pending | — | — | V4 §A.3 |
| 22 | Form input preservation across POST handlers | 4 | pending | — | — | V4 §A.3 sweep |
| 23 | Shop creation form too thin | 4 | pending | — | — | shop_type/mining_setup |
| 24 | CSRF tokens | 4 | deferred-to-followup | — | — | separate security pass |
| 25 | New-user onboarding banner | 5 | pending | — | — | new partial |
| 26 | Promote no-nation guidance | 5 | pending | — | — | tied to fix 25 |
| 27 | Apply-for-Nation entry point | 5 | pending | — | — | banner on /nations |
| 28 | Banks in navbar | 5 | pending | — | — | new nav item |
| 29 | Loans in navbar | 5 | pending | — | — | new nav item |
| 30 | Distribute in navbar (leader-only) | 5 | pending | — | — | V4 §N.5 |
| 31 | Promote pending-nation status | 5 | pending | — | — | visual emphasis |
| 32 | Mobile nav grouping | 7 | pending | — | — | V4 §F.2 |
| 33 | Sub-toggle pattern for sections | 7 | pending | — | — | tied to fix 32 |
| 34 | Breadcrumbs | 7 | pending | — | — | new |
| 35 | Favicon | 7 | pending | — | — | static asset |
| 36 | Open Graph meta tags | 7 | pending | — | — | base.html |
| 37 | Stop auto-dismissing errors | 8 | pending | — | — | V4 §F.4 |
| 38 | Standardize empty-state icons | 8 | pending | — | — | hygiene |
| 39 | Filter recent transactions on dashboard | 8 | pending | — | — | UX |
| 40 | Quick Actions visual hierarchy | 8 | pending | — | — | UX |
| 41 | Footer dynamic year | 8 | pending | — | — | trivial |
| 42 | Logout fallback form | 8 | pending | — | — | progressive enhancement |
| 43 | Wallet copy progressive enhancement | 8 | pending | — | — | data-copy attr |
| 44 | Pass user to docs templates | 9 | pending | — | — | V4 §N.1 |
| 45 | Cookie secure=True doc comment | 9 | pending | — | — | V4 §N.6, comment only |
| 46 | requirements-dev.txt for pytest+httpx | 10 | pending | — | — | V4 §N.8 |

### Unassessed (acknowledged, no fix in this run)
- UNASSESSED.1: Real-browser visual rendering (curl driver only)
- UNASSESSED.2: Concurrency / race conditions
- UNASSESSED.3: Real production data behavior
- UNASSESSED.4: Cloudflare/Pi end-to-end behavior under TLS

### Deferred-to-followup
- 11: Leadership-transfer flow (needs design input from Parker)
- 24: CSRF tokens (separate security pass)
