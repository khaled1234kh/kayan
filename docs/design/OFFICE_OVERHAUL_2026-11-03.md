# KAYAN TrustGate — Complete 3D Office Environment Overhaul

## Objective

I want you to perform a comprehensive visual and architectural refinement of the 3D environment where KAYAN's five virtual employees work.

I reviewed the latest front-facing and isometric screenshots. Although the interface has improved, **the office environment itself still does not look sufficiently polished for our graduation demonstration**.

I want KAYAN to look like a professionally designed cybersecurity operations center, not a basic 3D prototype.

Add the following tasks to the existing `TODO.md`, preserving all previous tasks, completion states, and evidence.

Treat the most serious geometry and visibility problems as P0 priorities.

You have permission to improve the environment beyond the specific issues I mention if those improvements meaningfully increase its quality.

Do not simply make the minimum corrections. Evaluate the scene as a complete environment.

---

## P0 — Architectural Geometry and Environment

### 1. Fix the exterior skyline and protruding background geometry

This is one of the most obvious problems.

In the angled screenshot, the blue-gray background panel behind the glass windows visibly extends above the rear wall and beyond the physical boundaries of the office.

This makes the building look incorrectly assembled.

Required work:

- Inspect the skyline backdrop, window geometry, exterior panels, and surrounding building shell.
- Determine exactly why the background extends beyond the architectural boundaries.
- Correct the actual geometry or rendering configuration rather than hiding the problem from one camera angle.
- Ensure the exterior scene remains properly behind the windows.
- Eliminate visible floating rectangular panels, unintended intersections, exposed edges, and misplaced meshes.
- Verify correct placement from the front, isometric, side, and elevated camera angles.
- Inspect mesh bounds, depth ordering, transparency, and clipping where applicable.

If the skyline is implemented using a large flat plane, consider replacing it with a better technique, such as a properly contained skybox/environment, layered background, or distant 3D city geometry.

Choose the simplest solution that produces convincing results.

### 2. Redesign the exterior city environment

The exterior has improved compared with the earlier yellow-window buildings, but it still looks flat and artificial.

Make the city visible through the windows look believable.

Consider:
- Varied building heights and silhouettes.
- Better building spacing and proportions.
- Realistic depth separation.
- Subtle atmospheric perspective.
- Natural differences in building materials.
- More coherent sky and horizon presentation.
- Appropriate exterior lighting.
- More convincing reflections and transparency.

The skyline should complement the office, not distract from it.

A restrained architectural exterior is preferable to an elaborate but obviously fake city.

Avoid enormous textures or expensive effects that unnecessarily reduce performance.

### 3. Fix walls obstructing important areas

The current office has large, solid black exterior walls.

In the angled screenshot, the front/right wall hides a substantial portion of the Reporting workstation and surrounding floor.

This reduces visibility and makes parts of the office difficult to inspect.

Investigate:
- Wall height and thickness.
- Visibility from intended presentation angles.
- Camera-dependent architectural cutaways.
- Transparency or occlusion treatment.
- How the outer shell interacts with internal partitions.
- Whether wall geometry should change between overview and close-up views.

Implement a coherent architectural cutaway system that preserves the appearance of a real office while keeping the important workstations visible.

Do not remove the building structure indiscriminately.

### 4. Improve camera framing and composition

The two screenshots reveal significant differences in workstation visibility depending on camera position.

The front view compresses the depth of the office. The angled view reveals more of the layout, but also exposes architectural problems and hidden workstations.

Revisit the camera system completely.

Improve:
- Default camera position.
- Camera angle and field of view.
- Office scale within the available viewport.
- Centering and composition.
- Orthographic versus perspective presentation, if relevant.
- Camera near/far clipping.
- Orbit limits.
- Zoom limits.
- Reset View behavior.
- Selected-agent camera focus.

Provide a high-quality default overview that presents all five employees clearly.

The office should occupy the available screen space effectively without clipping the architecture.

Consider useful camera presets such as:
- Overview
- Isometric
- Front
- Selected workstation

Preserve intuitive orbit and zoom controls.

### 5. Ensure all five employees remain visible

The office has five important characters:

- Planner Agent
- Recon Agent
- Web-App Agent
- Network Agent
- Reporting Agent

These are the core characters of our graduation project.

Their workstations must be identifiable and visually accessible.

Test their visibility from the default camera and each intended presentation preset.

Avoid having:
- Walls completely hide characters.
- Monitor geometry obstruct faces unnecessarily.
- Partitions overlap labels.
- Desks or chairs intersect characters.
- Characters appear outside their designated workstations.
- Camera framing crop essential parts of the team.

The environment should help viewers understand how the five agents cooperate.

---

## P1 — Office Interior and Art Direction

### 6. Establish a professional visual identity for the office

The overall scene should resemble a modern cybersecurity operations center.

Aim for a sophisticated environment with:
- Professional architectural materials.
- Cohesive dark and neutral colors.
- Restrained turquoise/cyan lighting accents.
- Carefully selected furniture and decorative details.
- Realistic office proportions.
- Well-defined workstations.
- Consistent environmental lighting.

Avoid overly futuristic, cartoonish, or gaming-oriented design choices.

Use a coherent art direction rather than adding unrelated visual features.

### 7. Improve lighting substantially

The current environment has several dark areas where details are difficult to distinguish.

Create a balanced lighting setup that makes the office attractive while preserving the dark cybersecurity aesthetic.

Evaluate:
- Ambient illumination.
- Key and fill lights.
- Workstation lighting.
- Monitor illumination.
- Window and exterior lighting.
- Shadow softness.
- Contact shadows.
- Material highlights.
- Color temperature.
- Tone mapping and exposure.

Ensure characters, desks, monitors, and architectural details remain visible.

Do not overuse neon strips, excessive bloom, or unrealistic glowing effects.

The environment should also look attractive in static screenshots for our presentation.

### 8. Improve glass partitions and window materials

The internal glass partitions currently look pale, with broad gray/white surfaces that sometimes obscure the workstations.

Review:
- Glass transparency.
- Reflection strength.
- Roughness.
- Edge highlights.
- Frame dimensions.
- Depth sorting.
- Overlapping transparent surfaces.
- Visibility of objects behind glass.

Make glass look like glass, not semitransparent white walls.

Preserve enough visual separation for the room layout to remain understandable.

### 9. Improve the floor, ceiling boundaries, and exterior shell

Inspect the overall construction of the office.

Look for:
- Unfinished floor edges.
- Floating geometry.
- Overlapping surfaces.
- Incorrect wall intersections.
- Inconsistent architectural thickness.
- Misaligned window frames.
- Missing or unrealistic structural details.
- Abrupt transitions into the black background.
- Unnatural shadows.

The office should appear intentionally constructed from every supported viewing angle.

Decide on a consistent open-roof/cutaway presentation instead of combining incomplete exterior architecture with an exposed interior.

### 10. Improve each workstation

The desks currently have recognizable computers, chairs, and a few accessories, but the workspaces still feel sparse and repetitive.

Make them more convincing.

Add or refine details where appropriate:
- Desk materials and proportions.
- Monitors and monitor stands.
- Keyboards and mice.
- Chairs and seating positions.
- Desk lighting.
- Cable management.
- Small professional accessories.
- Floor and desk contact shadows.
- Workstation-specific arrangements.

Give each agent's station a subtle identity aligned with its responsibility.

For example:
- Planner: coordination and overview.
- Recon: discovery and infrastructure mapping.
- Web-App: application analysis.
- Network: network and service analysis.
- Reporting: evidence and assessment reporting.

These visual differences must not imply features the application does not actually implement.

Use restrained details rather than overwhelming the environment with decorations.

### 11. Improve the virtual employees

Audit all five character models.

Evaluate:
- Model quality and consistency.
- Scale and body proportions.
- Clothing and materials.
- Seating posture.
- Chair and desk alignment.
- Hand and keyboard placement.
- Character visibility.
- Animation quality.
- Lighting on faces and bodies.
- Clipping and intersections.

The employees should appear naturally seated and working.

If idle, working, and completed animations exist, refine their transitions and ensure they reflect real agent state.

Do not fabricate activity to make the office look busy.

### 12. Refine the floor markings and status indicators

The office includes cyan/yellow floor lines and circular indicators near workstations.

Their meaning is not immediately clear.

Determine whether they represent:
- Agent selection.
- Workstation status.
- Communication between agents.
- Architectural decoration.

Then make their appearance consistent with their intended purpose.

If they are decorative, reduce their prominence or remove them.

If they communicate agent state, ensure the state is accurate and understandable.

Avoid visual elements that appear meaningful but have no actual functionality.

---

## P1 — Interaction and Demonstration Quality

### 13. Improve floating agent labels

The current agent labels are useful but need refinement.

Improve:
- Text size and readability.
- Positioning.
- Consistent height.
- Spacing from characters.
- Contrast.
- Overlap handling.
- Camera-angle behavior.
- Hover and selection states.

Labels should remain associated with the correct employees as the camera rotates.

Explore appropriate screen-space labels or carefully controlled world-space labels.

The chosen approach must avoid labels floating awkwardly or becoming hidden behind architecture.

### 14. Improve agent-selection interactions

Selecting an employee should feel intentional and polished.

Consider:
- Clear hover feedback.
- Subtle selection highlighting.
- Smooth camera focusing when appropriate.
- Correct synchronization with the Agent Session panel.
- A clear way to return to the overview.
- Reliable interaction through glass partitions.
- No accidental selection of unrelated geometry.

Keep interactions responsive and predictable.

### 15. Make the office communicate the multi-agent workflow

This is especially important for our graduation presentation.

The 3D environment should help professors understand what each agent does and how work progresses through the team.

Improve the presentation of genuine states:
- Idle
- Planning
- Working
- Waiting
- Completed
- Failed or blocked

Consider subtle, data-driven cues on workstations, monitor displays, labels, or selection indicators.

Do not build a fake simulation disconnected