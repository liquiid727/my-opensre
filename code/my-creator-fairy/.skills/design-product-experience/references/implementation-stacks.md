# Product Introduction Implementation

## Slidev Default

Use Slidev for numbered routes, talks, technical sharing, and Vercel-hosted presentation pages.

Recommended stack:

- Slidev CLI
- Vue 3
- `@slidev/theme-seriph` or a product-specific theme
- UnoCSS utility classes
- Shiki code highlighting
- Carbon or an existing icon library

Keep most content in `slides.md`. Extract Vue components only for repeated interactive structures such as architecture reveals, terminal walkthroughs, or progress timelines.

Global frontmatter should define:

- Theme
- Color schema
- Background
- Title and description
- Default transition
- Drawing persistence
- MDC support when needed

## React Or Vue Narrative Site

Use a responsive scrolling site when mobile reading and search indexing matter more than presenter control.

Translate each slide chapter into a full-width content band. Preserve the story order, diagrams, and progressive explanation, but replace fixed dimensions with responsive grid and container constraints.

Use CSS for small transitions. Use the existing motion library only for guided architecture walkthroughs or shared-layout continuity.

## Content Model

Separate:

- Product claims
- Evidence and source links
- Chapter order
- Slide content
- Visual semantics
- Speaker notes
- CTA targets

Do not encode claims inside animation scripts.

## Vercel Deployment

For a static Slidev build:

```json
{
  "rewrites": [
    { "source": "/(.*)", "destination": "/index.html" }
  ],
  "buildCommand": "npm run build",
  "outputDirectory": "dist"
}
```

Required package scripts:

```json
{
  "scripts": {
    "dev": "slidev --open",
    "build": "slidev build",
    "export": "slidev export"
  }
}
```

Verify direct numbered routes, browser refresh, assets, PDF export, and metadata.

## Performance

- Reserve dimensions for images and diagrams.
- Avoid loading large videos or animation libraries on every slide.
- Lazy-load non-current slide media where supported.
- Prefer system or limited font families.
- Test the presentation on the actual projector viewport and a common laptop viewport.

## Testing

Use browser automation to verify:

- First, middle, and final numbered routes
- Previous and next navigation
- `v-click` sequence and complete state
- Copy and external links
- Presenter and overview modes
- Desktop framing and public mobile fallback
- Reduced motion
- No console errors or missing assets
