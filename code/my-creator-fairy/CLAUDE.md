# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **SpecOS agent team kit** — a spec-driven development orchestration framework, not a traditional application. It defines agents, roles, rules, skills, workflows, and spec templates that govern how AI agents collaborate on software delivery. The project operates in **GoalSpec** mode (workflow-driven, 6-step goal loop: PRD → Spec → Issues → Goal → Review → Ship).

The default language is **zh-CN** (Chinese). Respond in Chinese unless told otherwise.

## Architecture

### Delivery Chain

Every change must preserve traceability through this chain:

```
draft → design → roadmap/epic → feature spec → implementation → review → merge
```

If any link is skipped, call it out explicitly.

### Agent System

- **Coordinator**: `pola` — classifies requests, selects roles from `.agents/manifest.yaml`, dispatches work
- **Main agents**: `architecture-agent`, `implementation-agent`, `deployment-agent`, `testing-agent`
- **Specialist agents**: `spec-editor`, `ddd-domain-agent`, `openapi-agent`, `db-migration-agent`, `ui-design-agent`, `reviewer`, `qa-agent`, plus test-type specialists (unit, playwright, e2e, performance, concurrency)
- Agent roles are defined in `.agents/roles/`, canonical prompts in `ai/agents/`
- `.agents/manifest.yaml` is the **sole registry** for available roles, skills, context includes, and delegation rules — do not invent ad-hoc roles

### Three Operating Modes

| Mode | Use case | Token cost |
|------|----------|------------|
| **LiteSpec** (default) | Solo/small team, MVP, fast iteration | Low |
| **GoalSpec** | Issue-driven 6-step loop (prd→spec→issues→goal→review→ship) | Low-moderate |
| **EnterpriseSpec** | QA-heavy, audit, compliance, multi-team | High |

Mode overlays live in `.agents/modes/<mode>/manifest.overlay.yaml`.

### Context Loading Order

Read context in this order before making changes:

1. `README.md`
2. `.rules/project.md` and `rules/`
3. `docs/spec-modes/` and `current/`
4. `spec-draft/`
5. `design/`
6. `specs/roadmap.md` and `specs/`
7. `implementation/`, `reviews/`, `tests/`
8. `ai/agents/` and `.agents/`

### Key Directories

- `spec-draft/` — intake drafts (human-authored, do not overwrite without permission)
- `design/` — stable platform/system design truth (one doc per platform)
- `specs/` — roadmap, feature specs by ID (e.g., `specs/RP-001-event-ingestion/spec.md`), templates in `_template/`
- `current/` — active delivery workspace and handoff state
- `implementation/` — implementation evidence by spec ID
- `reviews/` — review evidence by spec ID
- `tests/` — plans, scenarios, Bruno API tests, performance, concurrency results
- `rules/` — canonical reusable rules (frontend, backend, UI, CI, testing, shared)
- `.rules/` — agent-facing rule index; `.rules/project.md` is the compact entrypoint
- `.skills/` — scoped skills (architect-review, test-plan, DDD, Bruno API, etc.)
- `.specos/` — SpecOS manifest and workflow definitions
- `scripts/checks/` and `scripts/orchestration/` — validation and orchestration scripts

## Validation Commands

For `spec-web-ui/` (when present):
```bash
npm run test    # run tests
npm run build   # build check
```

Smoke check for agent kit integrity:
```bash
npx specos check
```

For spec/rule changes: manually verify cross-links, naming consistency, and scope alignment.

## Working Conventions

- **Requirement intake**: new requirements go through `spec-draft/requirement-intake-flow.md` — classify as draft/spec/implementation/test/review before editing
- **Role loading**: only load a role's declared `role_prompt`, `canonical`, `skills`, and `context_includes` — do not expand unbound skills
- **Human-authored content**: never overwrite drafts, specs, reports, or review notes without explicit permission (`protect_human_authored_files: true`)
- **Traceability**: every generated artifact must trace back to a spec, draft, or rule
- **Feature specs** must include: meta, goal, why, out-of-scope, deliverables, domain model, API, DB impact, test plan, definition of done
- **Spec IDs** follow the pattern `RP-001` and are indexed in `specs/roadmap.md`
- **Templates**: use `specs/_template/`, `tests/_template/`, `design/_template/`, `implementation/_template/` rather than ad-hoc formats
