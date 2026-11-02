Message to the agent: UI redesign (top priority alongside the Planner)

The current console UI cannot be shown to the doctor. It is cluttered, low-contrast and inconsistent, and the planning dialog is a wall of text. Treat a professional, calm and readable UI as a demo blocker, not optional polish. Keep the 3D office as the hero, and keep every honesty label and limit already in the project. Restructure the presentation, not the claims.

Design reference: a security operations product in the style of Linear, Vercel or CrowdStrike Falcon. That means a dark neutral theme, one accent color, generous spacing, clear hierarchy, and very little text on screen at once.

1. Design system first (one source of truth, applied everywhere)

Define tokens: background layers (
#0B0F14 base, 
#111821 panels, 
#1A2430 raised), one accent (cyan or teal), semantic colors (green allow, red deny, amber waiting/queued), and text levels (primary 
#E6EDF3, secondary 
#9FB0C0). Body text must meet WCAG AA contrast (4.5:1). No more faint grey on black.
Use one font family, with a type scale of 12 / 14 / 16 / 20 / 28. Use 8px spacing steps, 12px radius on cards and 1px subtle borders. Replace the one-off colors and sizes scattered through the components.

2. Layout: three zones, each with one job

┌──────────────────────────────────────────────────────────────┐
│ KAYAN TrustGate      [Live | Planning | Audit]   ● Connected │  slim top bar
├───────────────┬────────────────────────────┬─────────────────┤
│ Engagement    │                            │ Agent panel     │
│ - status      │      3D OFFICE (hero)      │ - name/role/tier│
│ - lab target  │                            │ - current task  │
│ - [New        │  5 agents, labels clean,   │ - tabs:         │
│   assessment] │  no overlap                │   Activity |    │
│ - progress    │                            │   Findings |    │
│   5 stages    │                            │   Decision |    │
│               │                            │   Message       │
├───────────────┴────────────────────────────┴─────────────────┤
│ legend (small, one line)                    [Reset view]     │
└──────────────────────────────────────────────────────────────┘
The left card shows engagement status and a 5-stage progress strip (Planner → Recon → Web-App → Network → Reporting) with a state for each. The strip should clearly show a partial or failed run.
The right panel uses tabs instead of one long scroll. The Decision card (ALLOW/DENY, subject, action, audit ref) gets its own tab or pinned header, and long IDs are truncated with a copy button. Nothing is cut off.
Agent labels in the 3D scene are small, consistent pills that never overlap a desk or each other. The selected agent gets a clear accent outline.

3. Planning dialog → a guided 3-step workspace, not a scroll

Open it as a large centered panel or a right-side drawer, so the 3D scene stays partly visible.
A stepper header shows 1 Risk Plan → 2 Mitigation (A or B) → 3 Review & Export, with the current step highlighted and the next action as one primary button.
Step 1: optional context in a clean two-column form (collapsed by default, with a “Use sample” button). Results show as three cards, each with a short title, one plain-language sentence, a reference chip (e.g. T1213.006) and a small “Hypothesis, not tested” badge.
Step 2: a segmented control Option A · Direct mitigation | Option B · From assessment. Show recommendations as cards in a list with a toggle for inclusion, a framework chip (Defense in Depth / Zero Trust) and the points on the right. A sticky summary bar shows the total, for example “3 included · 4 illustrative points”.
Step 3: review the selection and export.
Show the disclaimer (“Illustrative relative effort/cost only. Points are comparison weights, not prices, quotes or measured implementation effort.”) verbatim, as a visible info banner above the points total. Do not hide or shorten it.
Demote long explanatory paragraphs to a “How this works” expander or tooltip. Show one short evidence-basis badge per section (“Hypothetical, no testing” or “From saved assessment, 2 verified findings”).

4. Content and wording cleanup

Fix pluralization (“1 illustrative point”), remove jargon like “Descending TF-IDF text relevance” from the main view (move it into the info expander), and use sentence case consistently.
Phase 1 risk titles must read as risks to a person, for example “Possible exposure of stored database data” with the ATT&CK technique as a reference chip. Do not change the retrieval, ranking or zero-policy-weight behavior, and keep them labeled as hypotheses. If the current retrieved names read poorly, improve only the display wording, not the claims.
Never show raw UUIDs or policy strings as main content. Show friendly labels, with the full value on hover or copy.

5. Demo/Presentation mode

The “Presentation” view should be a clean, deliberate flow with minimal chrome, readable at projector distance (minimum 16px body text), and no debug-looking text.
Provide clear empty, loading and error states (“No assessment running”, “Connecting…”, “Gate unavailable: recorded evidence mode”).

6. Verification (required)

Look at the actual rendered UI at 1920×1080, 1440×900 and 1280×720, plus a narrow width, and save before/after screenshots. Build and geometry checks are not visual acceptance.
Check no overlapping labels, no cut-off panels, no horizontal overflow, keyboard focus visible, and text contrast. Report anything you could not verify.

Guardrails (unchanged)

Keep all existing honesty labels, the “No grounding improvement was demonstrated. Preserve this failure.” statement, and the shared-model/no-training disclosures.
Don’t change policy, gate, taint or agent execution behavior for visual reasons. Don’t invent metrics, and don’t claim anything is perfect or fully live-ready.
Don’t touch the Remotion/video project or the legacy server/ folder. Don’t bypass Windows security controls. Check git status before staging.
Update the existing UI tests and checks for anything you change.

Order of work: design tokens → three-zone layout and agent panel → planning stepper → wording cleanup → rendered verification at all sizes. Send me screenshots after the layout and the planning flow, before polishing the details.

Since this is the layout the doctor will see first, ask the agent to show you screenshots before it finishes. That way you can redirect early instead of discovering problems at the end.