---
name: public-docs
description: Write and maintain the human-facing documentation of a project under docs/ — feature and API references, the architecture overview, guides — where every doc declares the source paths it covers in frontmatter so it can be refreshed when they change. Modes: discover, gen <feature>, update, validate. Use when the user asks to document a feature or the project for people, and run `update` from /apogee:finish and /apogee:run-plan right after update-docs. Not for docs/apogee (that is update-docs, the agent's own context).
user-invocable: true
---

# Public Docs — documentation people read

`update-docs` keeps the agent's working context (`docs/apogee/`). This skill keeps the project's
**public** documentation: what a user or contributor reads under `docs/` (or wherever the project
keeps it). They serve different readers and never overlap.

**YOU MUST EXECUTE THIS WORKFLOW. Do not just describe it.**

## The contract: `sources:` frontmatter

Every doc this skill writes declares what it documents:

```markdown
---
title: "Authentication"
sources: [src/auth/, src/middleware/session.ts]
last_updated: 2026-10-20
---
```

`sources` is a list of paths or directory prefixes relative to the repo root. It is what makes
`update` deterministic: a doc is stale when a file under one of its sources changed after
`last_updated`. A doc without `sources` is human-maintained and only validated, never rewritten.

## Modes

```
/apogee:public-docs                 # discover gaps, then gen for each, then validate
/apogee:public-docs discover        # list the undocumented public surface, write nothing
/apogee:public-docs gen <feature>   # write one reference doc
/apogee:public-docs update          # refresh the docs whose sources changed (the work-loop hook)
/apogee:public-docs validate        # check existing docs against the code
```

Docs go under `docs/` by default (`docs/<feature>.md`, `docs/architecture.md`). If the project
keeps docs elsewhere (`documentation/`, a site under `website/`), match that location.

## discover

Read the project, don't grep for it. Identify entry points and the public surface in the
project's own terms: exported symbols, HTTP routes, CLI commands, public classes. Where a
JetBrains IDE is open, `mcp__idea__search_symbol` (load its schema with `ToolSearch` first)
gives the symbol list for an indexed language; otherwise read the entry files and the tests.
Skip private helpers and internal-only code.

Report what lacks a doc, grouped by module, with a one-line value judgment each (a public module
users call directly outranks a utility). In `discover` mode, stop here.

## gen <feature>

Read the feature's code and its tests (tests show real call sites), then write a reference for a
human reader using [references/generation-templates.md](references/generation-templates.md):
lead with what it does and how to use it, a runnable example, then the public contract. Set
`sources:` to the files and directories you actually read. Not the internal mechanics, not line
numbers (they rot); semantic signposts only.

The architecture overview is an ordinary doc: `docs/architecture.md` with `sources: [src/]`
(or the project's top-level code dirs), written from the template's architecture-overview section.

## update (the work-loop mode)

1. Base: in a git-flow repo the `gitflow.branch.develop` branch, else `main`; the changed set is
   `git diff --name-only <base>...HEAD` plus the working tree (`git diff --name-only HEAD`).
2. Collect every `*.md` under the docs location with a `sources:` list. None → say "no public
   docs declare sources; nothing to update" in one line and stop. This is the common case in a
   project that never ran `gen`, and it is not an error.
3. A doc is affected when any changed path equals or starts with one of its sources.
4. For each affected doc: re-read its sources, rewrite the AUTO-GENERATED sections and any claim
   the diff invalidated, preserve HUMAN-MAINTAINED sections verbatim, bump `last_updated`.
5. Report: docs refreshed, docs untouched, and any changed public surface that no doc covers
   (a `gen` candidate; don't generate it unasked).

Commit the result through `apogee:git-commit`, on the work branch, as its own `docs:` commit.

## validate

Apply [references/validation-rules.md](references/validation-rules.md): referenced symbols still
exist, examples still match signatures, internal links resolve, `sources:` paths still exist,
no stale "as of" claims. Report inline, grouped by severity; do not silently rewrite
human-maintained prose.

## Key rules

- **Human reader first.** Guides and references, not agent context and not coverage gates.
- **Document the public contract.** Skip private helpers.
- **Always show usage.** A reference without a runnable example is a stub; don't write stubs.
- **Semantic signposts, no line numbers.**
- **`sources:` is mandatory on generated docs.** It is the only thing that lets `update` find them.
- **Preserve human-maintained sections.** Section markers in the templates reference.

## Reference documents

- [references/generation-templates.md](references/generation-templates.md) — reference doc and architecture overview templates, section markers
- [references/validation-rules.md](references/validation-rules.md) — doc-vs-code validation rules
