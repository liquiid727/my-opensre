---
name: design-product-experience
description: Design and implement product introduction experiences for AI SaaS, developer tools, agent platforms, creator tools, and web products. Use when Codex needs to create a Slidev presentation, Vercel-hosted product introduction, technical product story, launch deck, interactive product walkthrough, or narrative landing page with section structure, visual system, progressive reveals, motion, calls to action, and React, Vue, or Slidev implementation guidance.
---

# Design Product Introduction

Create product introduction pages and technical presentation experiences similar to a polished Vercel-hosted Slidev deck. Focus on explaining a product, not designing its authenticated operational application.

Generate a specification by default. Build the actual page or deck when the user asks for a demo or implementation.

## Workflow

### 1. Establish product truth

Inspect supplied material and source repositories. Extract:

- Product category and literal product name
- Audience and current problem
- Core mechanism and differentiating capabilities
- Alternatives users already understand
- Real examples, workflows, proof, and constraints
- Desired ending action: install, open docs, request access, start trial, or view source
- Target format: Slidev deck, presentation-style microsite, or scrolling introduction page

Do not invent metrics, customers, integrations, benchmarks, commands, or security claims. Mark unsupported content as `Evidence needed`.

### 2. Choose the presentation surface

| Signal | Default surface |
| --- | --- |
| User references slides, a numbered route such as `/26`, a talk, PPT, or technical sharing | Slidev deck deployed as a static Vercel site |
| User requests a product introduction website or launch story | Responsive React/Vue narrative page |
| User requests both presentation and public reading | Slidev presentation plus responsive reading route |

Do not generate dashboards, work queues, editor shells, or authenticated application flows unless they appear only as product screenshots or walkthrough examples.

### 3. Select narrative patterns

Read [references/pattern-library.md](references/pattern-library.md). Select only patterns that solve a concrete communication problem. A typical introduction uses three to five patterns.

Read [references/domain-playbooks.md](references/domain-playbooks.md) for product-specific priorities.

### 4. Build the story before styling

Define the audience's decision sequence:

`Why care -> what it is -> how it works -> why this approach -> where it helps -> how to adopt -> what to do next`

Read [references/page-structure.md](references/page-structure.md). Map each decision to one slide or one page section. Give every slide a single communication responsibility.

For each slide or section define:

- Audience question
- One-sentence takeaway
- Required content and evidence
- Primary visual object
- Reveal order
- Speaker or reading transition
- Responsive or export behavior

### 5. Define the visual language

Use a restrained product-specific system:

- One dark or light canvas appropriate to the domain
- One primary brand accent
- Stable semantic colors for information, success, warning, risk, and intelligence
- Serif or display typography only when it supports presentation character
- Monospace type for commands, traces, schemas, and code
- Cards only for comparisons or repeated concepts, not every section

Keep text concise enough to present. Use diagrams, real product states, commands, tables, and workflows as primary visuals.

### 6. Design motion as presentation logic

Read [references/motion-system.md](references/motion-system.md). Use motion to control attention and reveal causality.

Specify:

- Page transition
- `v-click` or manual reveal order
- Elements that persist between reveals
- Interaction and hover feedback
- Auto-play behavior, if any
- Reduced-motion and static export state

Never hide essential meaning behind animation. Avoid decorative looping effects.

### 7. Define implementation

Read [references/implementation-stacks.md](references/implementation-stacks.md).

For Slidev, define theme, frontmatter, layouts, utility classes, components, code highlighting, icons, navigation, export, and Vercel rewrites. For React or Vue, translate slides into responsive full-width narrative sections without fixed-canvas scaling.

### 8. Validate and deliver

Read [references/quality-gates.md](references/quality-gates.md). Render the output with [templates/experience-blueprint.md](templates/experience-blueprint.md).

Use:

- [templates/page-section-spec.md](templates/page-section-spec.md) for slide-by-slide contracts
- [templates/motion-plan.md](templates/motion-plan.md) for reveal timelines
- [templates/technical-plan.md](templates/technical-plan.md) for implementation and deployment
- [templates/slidev-starter.md](templates/slidev-starter.md) when creating a Slidev source file

Write in the user's language. Keep claims short, literal, and grounded in supplied facts.

## Required Output

Include:

1. Product positioning and audience
2. Selected narrative patterns
3. Chapter-level story arc
4. Slide or section map
5. Detailed slide specifications
6. Visual system and reusable layout grammar
7. Reveal and transition plan
8. Slidev, React, or Vue implementation plan
9. Responsive, presentation, and PDF-export behavior
10. Vercel deployment configuration
11. Acceptance criteria and evidence gaps

## Guardrails

- Generate a product introduction, not the product's internal application.
- Use the product name or literal category as the opening headline.
- Show actual mechanisms, outputs, workflows, or code instead of generic atmospheric visuals.
- Keep slides visually stable while information reveals progressively.
- Avoid marketing-site boilerplate such as logo walls, fake testimonials, or pricing unless supplied.
- Do not copy source-product branding, wording, names, colors, or links.
- Do not treat a fixed 16:9 Slidev canvas as a responsive mobile website.
- Provide a readable alternate route when a public site must work well on phones.
