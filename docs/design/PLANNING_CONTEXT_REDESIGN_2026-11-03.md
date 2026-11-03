# Additional P0 TODO — Completely Redesign the Planning Context Experience

Add this to the existing KAYAN UI/UX refinement TODO list as a **high-priority task**.

I am not satisfied with the current "Start with your context" interface inside the Planning Workspace.

It currently looks like a basic developer form containing six large textboxes, excessive explanatory text, inefficient spacing, and a long internal scrollbar.

I want you to redesign this into a **premium, intuitive, engaging, and professional organization-profile setup experience**.

The user should feel like they are configuring a sophisticated cybersecurity risk-planning platform, not filling out a generic HTML form.

## 1. Rethink the entire interaction

Do not simply change colors, increase padding, or make the textboxes larger.

Redesign the actual experience of entering organizational context.

Consider a guided workflow that helps the user describe their organization progressively, with clear navigation and meaningful feedback.

The six existing context fields must remain supported:

1. Company size
2. Departments
3. Infrastructure summary
4. Network architecture
5. Data storage
6. Customer touchpoints

However, they do not have to appear as six consecutive textareas.

Choose a better interaction pattern based on usability.

For example, organize the fields into three logical sections:

**Organization Profile**
- Company size
- Departments

**Technical Environment**
- Infrastructure summary
- Network architecture

**Data & Customer Interaction**
- Data storage
- Customer touchpoints

A guided three-stage setup, well-designed cards, or a hybrid structured-input experience may be appropriate.

Avoid making the process unnecessarily long or introducing excessive clicks.

## 2. Improve the actual input experience

Currently, the user is expected to know what to write in every field without enough meaningful guidance.

Add helpful guidance such as:

- Short, human-friendly explanations.
- Realistic example values.
- Useful placeholder text.
- Optional suggestions or selectable examples.
- Clear distinctions between required and optional information.
- Appropriate multiline inputs for longer technical descriptions.
- Comfortable text editing and keyboard navigation.

Where useful, provide structured choices alongside free-text entry.

For example:

**Company Size**
- Startup
- Small
- Medium
- Large
- Enterprise
- Optional employee count and description

**Infrastructure**
- On-premises
- Cloud
- Hybrid
- Optional details about technologies and services

**Data Storage**
- Relational databases
- Cloud storage
- On-premises storage
- Sensitive customer data
- Optional custom description

These choices should help users describe their situation, not restrict them to predefined categories.

Preserve compatibility with the existing six-field backend contract.

## 3. Create a polished visual layout

The current modal wastes horizontal space and forces excessive vertical scrolling.

Improve:

- Modal width and proportions.
- Information hierarchy.
- Section organization.
- Field widths and heights.
- Typography and contrast.
- Spacing between controls.
- Navigation and progress indication.
- Scrolling behavior.
- Header and footer layout.
- Responsive presentation.

Use a modern, restrained, professional interface consistent with the broader KAYAN design system.

Avoid excessive borders, repetitive labels, unnecessary instructions, and decorative elements that add no value.

Make the primary action obvious.

## 4. Make it engaging without being gimmicky

The experience should feel intelligent and responsive.

Consider adding:

- Clear progress through the organization profile.
- Contextual guidance while completing sections.
- A concise organization summary before generating the risk plan.
- Easy editing of previously entered information.
- A meaningful indication of which context sections have been supplied.
- Subtle transitions between sections.
- Clear loading and completion feedback.

Do not introduce fake AI analysis, invented readiness scores, artificial risk percentages, or misleading security assessments.

Any progress indicators must represent genuine user completion or system state.

## 5. Improve the "Use sample" feature

The existing "Use sample" button is not sufficiently informative.

Improve it so that users understand what will happen.

Ideally:
- Offer a preview of the sample organization.
- Explain that it is fictional demonstration data.
- Allow the user to load the sample easily.
- Avoid silently overwriting existing user input.
- Provide a clear confirmation if existing content would be replaced.
- Permit users to customize sample data afterward.

Consider offering a small number of realistic organization profiles if this meaningfully improves the demonstration, such as e-commerce, healthcare, and financial services.

Do not overcomplicate the experience with a large template library.

## 6. Fix context preservation and editing

The earlier exported JSON contained truncated and accidentally concatenated descriptions.

Investigate and correct the underlying cause.

Verify that:
- Typing works normally.
- Pasting replaces selected text correctly.
- Long descriptions are preserved within documented limits.
- Switching sections does not discard information.
- Using samples does not unexpectedly combine old and new text.
- Submitted context matches the exported context.
- Closing and reopening the workspace behaves predictably.
- Input length limits are communicated clearly.

Remove repetitive explanatory text such as the current cursor-editing instructions from beneath every field. Use concise helper text only where necessary.

## 7. Clarify the user journey

The current interface contains "Use saved assessment" alongside "Generate Risk Plan", which can make the user's options confusing.

Make the distinction clear:

**Option A — Plan from organizational context**
Generate hypothetical cybersecurity risks without target testing.

**Option B — Use a saved assessment**
Build recommendations from the verified results of an existing authorized assessment.

Users should understand these different evidence paths without needing to read lengthy technical disclaimers.

Preserve the existing security distinction: company descriptions have zero authorization weight and cannot grant scope or permission.

## 8. Improve the transition to results

After the user enters context and generates a plan, the transition should feel connected and intentional.

The resulting risk cards should:
- Reference relevant information from the organization description.
- Explain why each hypothetical risk was suggested.
- Display meaningful framework references.
- Clearly communicate uncertainty.
- Avoid presenting retrieval similarity as verified severity.
- Lead naturally into mitigation planning.

The entire journey should feel like one cohesive product experience:

**Organization Profile → Hypothetical Risk Analysis → Mitigation Planning → Review & Export**

## 9. Acceptance criteria

Do not mark this TODO as complete until:

- The redesigned interface has been implemented.
- All six context fields work correctly.
- The layout is genuinely improved, not just recolored.
- Users can enter long descriptions comfortably.
- Samples and editing behave correctly.
- Input values remain intact through submission and export.
- Navigation is clear and intuitive.
- The interface works at desktop, laptop, and narrow viewport sizes.
- Keyboard navigation and readable contrast are verified.
- The actual rendered interface is inspected in a browser.
- A complete context-to-export workflow succeeds.
- No existing TrustGate policy or authorization behavior is weakened.

Take screenshots of the old and redesigned interface and compare them.

**Make design decisions yourself where appropriate. Don't stop after implementing the minimum requested changes. Identify and fix additional UX problems you encounter.**

The goal is a planning interface that looks and feels like a professionally developed cybersecurity product that we can confidently demonstrate to university professors.

Keep this task in the existing TODO list alongside the broader sidebar redesign, 3D office improvements, agent-session panel polish, and full application visual audit.