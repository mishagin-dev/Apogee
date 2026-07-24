# ADR 0004 — Serena recommended as a non-JetBrains idea-mcp alternative; no integration built

**Status:** Accepted · **Date:** 2026-07-23

## Context

The `idea/` hook group and `apogee:idea-mcp` skill push the agent onto JetBrains' MCP server
(`mcp__idea__*`) specifically for token economy: precise, pre-indexed symbol lookups
(`search_symbol`, `get_symbol_info`, `get_file_problems`, `rename_refactoring`, plus PHP structural
search) instead of blind full-text grep or whole-file reads. Everything else idea-mcp offers
(Xdebug, DB introspection, Symfony/Doctrine/Twig tooling, run configs) is a JetBrains-only bonus, not
the core token-saving job. The open question this session: **is there a non-JetBrains, editor-
agnostic alternative that does that specific job** — precise symbol/reference lookup instead of
brute-force search — without requiring a commercial IDE process running?

This is a distinct question from [ADR 0003](0003-zed-no-parity-defer-idea-mcp-retirement.md), which
asked whether *Zed specifically* could replace idea-mcp (it can't — Zed exposes no editor-side
tool-provider API to external agents at all). This ADR is about general-purpose, IDE-independent
alternatives to the underlying capability, regardless of which editor the user is running.

**Research finding (2026-07-23):** [Serena](https://github.com/oraios/serena) is the clear
best-in-class candidate — 26.8k stars, MIT license, daily commits as of this writing. It wraps real
language servers (LSP) behind MCP tools (`find_symbol`, `get_symbols_overview`,
`find_referencing_symbols`, safe symbol-level rename/replace, LSP diagnostics) across 60+ languages,
including Swift (fixing a gap idea-mcp's own SKILL.md documents today — Swift opens as a generic
`WEB_MODULE` in JetBrains and isn't properly indexed) and PHP (via Intelephense or Phpactor). Unlike
idea-mcp's fully implicit "IDE is already open" activation, Serena needs a one-time
`serena project create --index` (or `serena init`) per project, and some language servers must be
installed separately (others, like Java's JDTLS, auto-download on first use). It has no equivalent
to JetBrains' full inspection catalog or the Xdebug/DB/Symfony/Doctrine/Twig bonus tooling — expected
and acceptable, since those aren't the core ask.

Other candidates surveyed and rejected as the primary recommendation:
- **Generic LSP-bridge projects** (`isaacphi/mcp-language-server` and similar) — real, but
  fragmented and low-adoption compared to Serena; each requires hand-installing and hand-configuring
  a language server per language/project, with no auto-detection.
- **ast-grep-mcp** and **ctags/gtags-based MCP servers** (e.g. `mcp-gtags-server`) — genuinely
  lighter-weight (no language-server daemon, near-zero setup), but structural/heuristic rather than
  semantic: they find syntactic matches or regex-tagged locations, not type-resolved
  references/definitions. Real complements for the exact case where even Serena's LSP backend is
  weak or absent (a niche today, but not the general answer), not substitutes for
  `search_symbol`/`rename_refactoring` in an indexed language.
- **Claude Code native capabilities** — as of 2026-07-23, Claude Code ships no first-party semantic
  code index or symbol-navigation tool of its own; this gap is still open industry-wide, not
  something the platform has absorbed.

## Decision

1. **Record Serena as the recommended non-JetBrains alternative/complement** for the token-saving
   symbol-lookup job idea-mcp currently does, should the user want an IDE-independent option in the
   future (e.g., for a project where no JetBrains IDE is ever opened).
2. **No integration is built as part of this ADR.** A `serena/` hook group mirroring `idea/`'s
   self-gating design is real, separate engineering work this ADR does not schedule — it would need
   its own design pass (see below), not a copy-paste of `idea/`'s mechanism.
3. If the user later wants this built, the self-gating trigger should **not** be assumed to inherit
   `idea/`'s `.idea/`-dir-plus-running-process check — Serena's activation signal is different
   (`.serena/project.yml` presence after the one-time init step, not a running IDE process check via
   `pgrep`), and needs its own design for: how the agent discovers Serena is available per-project,
   whether/how it coexists with idea-mcp when both could apply (e.g. a JetBrains project that also
   has Serena initialized — priority order isn't obvious), and what `mcp__serena__*` permission
   baseline `setup.sh` should carry (mirroring the `mcp__idea__*` precedent in
   [ADR 0002](0002-plugin-not-global-hooks.md)'s baseline-permissions amendment).

## Consequences

- No code, hook, or permission changes follow from this ADR — it records a research finding and a
  deferred recommendation, not a feature.
- If Serena is adopted later, record that as a dated Amendment to this ADR (matching the pattern in
  ADR 0002 and ADR 0003) rather than a fresh ADR, since it's the direct follow-through of the
  recommendation made here.
- Revisit this recommendation if Serena's maintenance trajectory changes materially, or if a more
  broadly-adopted alternative emerges — cite the new finding as a dated Amendment rather than
  re-researching from scratch each time.
