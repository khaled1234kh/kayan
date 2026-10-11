# KAYAN — Demo Recording Script

## Files
- prototype.html — enterprise console: Workforce, Task Board, TrustGate, Audit Log
- office.html — isometric operations floor (linked both ways)
- All state is in-memory. Press F5 to reset before any take or retry.

## Pre-recording checklist
- Fresh reload (F5) of the page being recorded
- Chrome fullscreen, bookmarks bar hidden (Ctrl+Shift+B)
- Windows Focus Assist on — no toasts during takes
- Network available (Google Fonts) — or verify the offline fallback once
- If a take fails: F5 and restart the take; state accumulates across actions

## Take A — Console arc (prototype.html)
1. Workforce — hold 3s. 6 seats, 4 active, AI spend EGP 326.
2. Task Board — hold 2s. T005 "Awaiting CEO" in the Approval column.
3. ATTACK 02 · INJECTION — modal: READ -> DENY -> incident recorded. Hold 3s.
4. ACKNOWLEDGE.
5. ATTACK 05 · DENIAL-OF-WALLET — orange BLOCKED, budget preflight. Hold 3s.
6. ACKNOWLEDGE.
7. ATTACK 07 · ESCALATION — red DENY, authority. Hold 2s. ACKNOWLEDGE.
8. APPROVE ORDER — chip flips to APPROVED, card dims, meta updates. Hold 2s.
9. Audit Log — hold 4s. Full trail with live timestamps. Closing shot of Take A.

## Take B — Office arc (office.html)
1. Establishing shot, no input, 3s: quiet floor, pulsing rings, room labels.
2. One slow pan across the floor (drag), 2s. Optional slight zoom toward Operations.
3. Hover Sales AI desk — label appears. Hold 1s. Click — inspector fills.
4. Click TrustGate room — rules R-01/02/03, LAST DECISION.
5. REPLAY ATTACK 02 · INJECTION — modal + red pulse on the rack. Hold 2s.
6. ACKNOWLEDGE — pulse stops, activity row logs.
7. Click CEO desk (Layla Hassan) — AWAITING APPROVAL. APPROVE ORDER — ring flips
   teal. Hold 2s.
8. OPEN CONSOLE -> Audit Log in prototype.html (optional if Take A ends there).

## Defense Q&A
- "Is the enforcement real?" -> "This is the operator surface. The enforcement
  engine is Months 3–4; we designed the interface first because it defines what
  the gateway must expose."
- "Why only 3 of 8 attacks?" -> "Distinct enforcement paths — data-flow taint,
  budget preflight, authority. The red-team harness covers all eight."
- "Where do the numbers come from?" -> "They are the proposal's numbers: EGP 326
  spend, EGP 40/200 caps, the Cedar forbid rule, the capability contract. Nothing
  on screen is invented."
- "Why isometric, not 3D?" -> "The proposal scopes the MVP as 2D/isometric; full
  3D is a declared post-graduation extension."
- "Do the two pages share state?" -> "In the prototype, state resets per view;
  shared state arrives with the persistence layer in Months 3–4."
