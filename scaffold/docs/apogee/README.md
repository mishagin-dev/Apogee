<!-- apogee:scaffold-stub: fill the Index section as files and directories appear -->

# docs/apogee — Apogee working memory (local-only)

Everything in this directory is personal AI-tooling context, kept out of git by Apogee. A
deliverable the project must keep (something that has to survive a fresh clone) goes to the
tracked `docs/` instead.

This file is the index. `/apogee:prime` reads it, so keep one line per directory and per file
worth knowing about: what it is, when to read it.

## ai-context/ (core, always present)

- `spec.md`, `project-structure.md`, `progress.md`, `deployment-infrastructure.md`: loaded by
  `/apogee:prime`; maintained by `/apogee:update-docs`.

## Working-memory directories

Created empty by `setup.sh` so the layout is visible from day one. Put a file in one, add a line to
the Index below; a file without an index line is invisible to the next session.

| Directory | Purpose |
|---|---|
| `domain/` | Subject-matter logic an agent cannot infer from code: finance rules, billing, scoring, regulatory constraints. One file per topic. |
| `design/` | Design sources (`.pen` files, images, mockups) and `design/design-system.md`: the design system as context for Claude — tokens, components, layout rules, voice. |
| `diagrams/` | Mermaid, draw.io, PNG. |
| `research/` | Dated reports, second opinions, comparisons: `YYYY-MM-DD-<topic>.md`. |
| `prompts/` | Reusable prompts and request templates (a finance-report prompt, a release-notes prompt). |
| `reports/` | Generated reports and other ceremony-free deliverables (Apogee RULES.md, "Files"). |

## Index

<!-- One line per entry: `path`: what it is, when to read it. Example:
- `domain/finance.md`: how invoices, refunds and VAT are computed; read before touching billing
- `design/design-system.md`: tokens and component rules; read before any UI work
- `design/app.pen`: main app screens (Pencil)
-->
