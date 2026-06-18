---
name: doc
description: 'Generate and maintain professional, human-readable documentation for a code project: feature/API reference, a code-map (architecture overview), and usage guides written for human readers. Validates docs against the code. Use to document a project for people (not agent context). Triggers: "doc", "document this", "code-map", "API docs", "generate documentation", "write docs", "find missing docs".'
user_invocable: true
---

# /apogee:doc — Professional Project Documentation

> **Purpose:** Generate and maintain documentation a **human** reads — feature/API reference, a
> code-map (architecture overview), and usage guides — and keep it honest against the code.

This is the human-facing counterpart to `/apogee:update-docs`, which maintains the agent's
`docs/apogee/ai-context/*` working context. Use `doc` for documentation your **users and contributors**
read; use `update-docs` for the agent's own project context. They serve different readers and do not
overlap.

**YOU MUST EXECUTE THIS WORKFLOW. Do not just describe it.**

## Quick Start

```bash
/apogee:doc                 # = all: discover gaps, generate, validate
/apogee:doc gen <feature>   # document one feature/module
/apogee:doc code-map        # generate the architecture overview
/apogee:doc validate        # check existing docs against the code
/apogee:doc discover        # list undocumented public surface, write nothing
```

Generated docs go under `docs/` by default (e.g. `docs/<feature>.md`, `docs/code-map.md`). If the
project keeps docs elsewhere (a `documentation/` dir, a site under `website/`), match that location.

## Commands

| Command | Action |
|---|---|
| `discover` | Find undocumented public API (functions/classes/endpoints) and report — no writes |
| `gen <feature>` | Read the feature's code, write a human reference doc to `docs/<feature>.md` |
| `code-map` | Write an architecture overview to `docs/code-map.md` |
| `validate` | Check docs vs code: stale claims, missing sections, broken links |
| `all` (default) | discover -> generate the gaps -> validate |

## Step 1: Scope the project

Read the layout before writing. Identify language(s), entry points, and the public surface.

```bash
ls package.json pyproject.toml go.mod Cargo.toml 2>/dev/null   # language/build
ls -d docs/ documentation/ 2>/dev/null                          # existing docs home
```

For an unfamiliar framework or library, consult Context7 MCP before documenting its APIs.

## Step 2: Discover the public surface

Find the public, human-relevant API that lacks docs (skip private/internal helpers):

```bash
grep -rn "^def [a-z]" --include="*.py" | grep -v "^def _"   # Python public functions
grep -rn "^func [A-Z]" --include="*.go"                      # Go exported functions
grep -rn "export function\|export class" --include="*.ts"    # TS exports
```

Report what is undocumented. In `discover` mode, stop here.

## Step 3: Generate (human reference)

For `gen <feature>` or each gap in `all`: read the code, understand behaviour and edge cases, and write
a doc for a human reader using the templates in
[references/generation-templates.md](references/generation-templates.md). Lead with what the feature
does and how to use it; include a runnable example. Document the public contract, not internal mechanics.

## Step 4: Code-map (architecture overview)

For `code-map`: write `docs/code-map.md` — a one-screen orientation for a new contributor (overview,
directory structure with purposes, key components + entry points, data flow, external dependencies). Use
**semantic signposts** (function/type names), never line numbers (they rot). Template in
[references/generation-templates.md](references/generation-templates.md).

## Step 5: Validate

For `validate` (and after generating): check docs against the code using
[references/validation-rules.md](references/validation-rules.md) — referenced functions/types still
exist, examples still match signatures, internal links resolve, no stale "as of <date>" claims. Report
issues; do not silently rewrite human-maintained prose.

## Step 6: Report

Tell the user, inline (no machine report file): docs generated/updated, the public surface still
undocumented, and any validation issues found. Let the user decide what to fix next.

## Key Rules

- **Human reader first** — guides and reference, not agent context (that's `update-docs`) and not
  coverage gates for CI.
- **Document the public contract** — skip private helpers and internal-only code.
- **Always show usage** — a doc without a runnable example is a stub.
- **Semantic signposts, no line numbers.**
- **Preserve human-maintained sections** — see the section markers in the templates reference.

## Examples

### Document one module

**User says:** `/apogee:doc gen authentication`

1. Scopes the project, finds the auth module.
2. Reads the public auth functions and their tests for usage patterns.
3. Writes `docs/authentication.md` with purpose, API reference, and a runnable example.
4. Validates the doc's signatures against the source.

**Result:** A human-readable auth reference under `docs/`.

### Refresh the architecture overview

**User says:** `/apogee:doc code-map`

1. Maps directories to purposes and traces the main data flow.
2. Writes `docs/code-map.md` with semantic signposts.

**Result:** A new-contributor orientation doc.

## Troubleshooting

| Problem | Cause | Solution |
|---|---|---|
| Discover lists too many items | Low existing coverage | Run `gen` on the highest-value public modules first; ignore internal helpers |
| Generated docs lack examples | No obvious usage in source | Read the tests for real call sites; ask the user for a canonical use case |
| Validation flags out-of-sync docs | Code changed after the doc was written | Re-run `gen` for the affected feature |

## Reference Documents

- [references/generation-templates.md](references/generation-templates.md) — human doc + code-map templates
- [references/validation-rules.md](references/validation-rules.md) — doc-vs-code validation rules
