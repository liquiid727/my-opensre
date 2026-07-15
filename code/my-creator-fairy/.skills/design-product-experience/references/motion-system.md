# Product Introduction Motion System

## Motion Roles

| Role | Behavior |
| --- | --- |
| Chapter change | Slide, fade, or shared-axis page transition |
| Progressive explanation | Presenter-controlled reveal with stable context |
| Causality | Highlight the relationship introduced by the current step |
| Emphasis | Short opacity, border, or color change |
| Feedback | Copy, navigation, or control confirmation |

## Slide Transitions

- Use `slide-left` for forward narrative movement.
- Use `fade-out` for conceptual resets, definitions, and conclusions.
- Use `slide-up` sparingly for escalation or chapter elevation.
- Keep the default transition around 400-550ms.

Do not assign a unique transition to every slide.

## Progressive Reveal

Use `v-click` for one meaningful item and `v-clicks` for ordered peer content. Reveal one semantic unit per audience beat. Existing content should remain fixed.

Use `v-click-hide` only when replacement is easier to understand than accumulation. Provide a complete final composition for PDF export.

## Custom Animation

Use custom CSS keyframes only for a meaningful signature moment such as a presenter-name reveal, architecture path, or final completion state.

Recommended duration bands:

- Hover and copy feedback: 100-180ms
- Item reveal: 250-450ms
- Page transition: 400-550ms
- Signature reveal: 800-1800ms

Avoid looping glows, background particles, simulated activity, and auto-playing required content.

## Reduced Motion

Under `prefers-reduced-motion: reduce`:

- Remove spatial page movement.
- Show all required slide content immediately.
- Replace reveal translation with instant display or a short fade.
- Stop auto-play and looping effects.

## Interaction

Make keyboard navigation, overview, presenter mode, and copy controls available. Interactive diagrams must also have labels and a complete static state.
