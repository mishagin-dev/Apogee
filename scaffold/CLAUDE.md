# [Project Name]

<!-- Customize this file for your project. This is the primary instruction set
     that Claude Code reads at the start of every session. Keep it focused on
     rules, decisions, and constraints — not documentation that belongs in
     docs/apogee/. -->

## 1. Critical Rules

- **Use Sub-Agents** for tasks spanning 3+ files or requiring parallel investigation.
- **Decompose complex work**: split a complex task or a batch of bugs into separate, focused units of work (in git-flow projects, one `feature/`/`bugfix/` branch each) instead of one big change. Run them sequentially when they touch overlapping files, or in parallel when their file sets are disjoint. State the split and the chosen order before starting. When a `feature/`/`bugfix/` branch's work is complete, finish it through `/apogee:merge` (it runs the docs/clean-tree guardrails, then delegates to the git-flow finish) — not hand-rolled merges; `release`/`hotfix` finish only on explicit request.
- **Always ask before**: git commits, breaking changes, major architecture decisions, deleting files.
- **Stop-and-Replan Rule**: If an approach fails or you discover unexpected complexity, stop and reassess rather than pushing through.
- **Use available skills proactively**: `/apogee:review-work` for code review, `/apogee:update-docs` after significant changes, `/apogee:deploy` for deployments.
- **Context7 first**: When working with external libraries, check Context7 for current documentation before relying on training data.
- **idea-mcp first** (only when the JetBrains IDE MCP `mcp__idea__*` is connected): prefer IDE tools — symbol search, inspections, refactoring — over terminal equivalents. Ignore entirely when the IDE is absent.
- **Language split**: user-facing dialogue in your working language; everything else — code, identifiers, comments, commit messages, docs, branch names, and anything sent to external tools (agy / CLIs) — in **English**. The `apogee:git-commit` skill is the canonical example (commit messages always English).
- **Git**: never `git push` (push manually after review); commit only via the `apogee:git-commit` skill (never `git commit -m` ad hoc). Exclude unrelated/generated files; never force-add `.gitignore`d files. In git-flow repos, run branch lifecycle through the `apogee:git-flow` skill and commit only on `feature/`/`bugfix/` branches — never on `main`/`develop`.
- **Git-ignored deliverables are ceremony-free**: a report, research note, or other output written to a **git-ignored path** (a folder in `.gitignore`, e.g. `reports/`, scratch, build outputs) is a deliverable-on-disk — it needs **no** br step, **no** git-flow branch, and **no** commit. The edit/branch/Stop gates already exempt such paths, so just write the file and stop; don't force it into the workflow or try to commit it.
- **Work honestly**: study existing code and reuse utilities before writing new ones; surface problems and trade-offs openly — never hide failures.

## 2. Communication Style

- Tone: professional, direct — courteous, not clinical. No emotional theatrics, no sycophancy.
- Acknowledge basic social exchanges (thanks, greetings) with a brief, genuine reply — courtesy
  isn't filler.
- No unearned praise on the user's ideas or questions, no apologies or self-deprecation, no
  conversational padding ("of course!", "great question!", "hope this helps") inside
  task-focused responses.
- No explaining the obvious.
- Response shape: fact → analysis → solution — no preamble, no unrequested closing summary.
- Error/bug reports: cause → location → fix. No commentary on fault or emotional state.
- Interpret the user's questions literally — don't assume context that isn't stated.
- Don't propose alternative architectures unless asked.

## 3. Operator Model

<!-- Describe how you and Claude collaborate. Optional but valuable for
     solo / AI-agent-driven workflows.

Example:

- **Role split.** I'm the decision-maker, director, and reviewer. AI agents
  (Claude + sub-agents) write the code. Build effort ≈ zero; cost is
  maintenance, debuggability, and decision overhead.
- **Evaluate by maintenance burden, not build effort.** "Too much code for
  a solo dev" is not a valid critique — pick libraries and architectures on
  technical merit.
- **Boundaries:** always ask before git commits, breaking changes, deleting
  files, and architecture decisions worth ≥1 day of rework to undo. -->

## 4. Key Architecture Decisions

<!-- Document settled decisions here so Claude doesn't relitigate them.
     Include brief rationale for each. -->

<!-- Tip: Also list decisions that are SETTLED so Claude doesn't relitigate them.
     Example: "REST over GraphQL — decided, don't suggest changing." -->

<!--
Example:
- **Authentication**: JWT tokens with refresh rotation. Why: stateless, scales horizontally.
- **Database**: PostgreSQL with RLS on all tables. Why: row-level security eliminates auth middleware bugs.
- **State management**: Server-side only. Why: single source of truth, no sync bugs.
-->

## 5. Tool Usage Rules

<!-- Map tasks to the correct tools for your project. -->

| Task | Use This |
|------|----------|
| Project onboarding / fill docs | `/apogee:init` (run once on a new project) |
| Library docs lookup | Context7 plugin (check FIRST) |
| Code intelligence / refactoring (JetBrains) | `apogee:idea-mcp` `mcp__idea__*` (when the IDE is connected) |
| Code review | `/apogee:review-work` skill |
| Second opinion | Ask for "second opinion" / "ask agy" (runs the `agy` CLI) |
| Documentation update | `/apogee:update-docs` skill |
| Deployment | `/apogee:deploy` skill |

## 6. Coding Standards

<!-- Keep only standards that are non-obvious or project-specific.
     Don't document standard language conventions — Claude already knows those. -->

- Follow the project's existing style, naming, and idioms; don't introduce new conventions without need.
- Comments only where the code cannot speak for itself (constraints, non-obvious decisions) — no narrating comments.
- No dead code, commented-out blocks, or unused imports in the result.
- KISS: pick the simplest solution that satisfies the requirement now; flat structure over nested unless nesting improves readability.
- YAGNI: no speculative functionality, config, or flags without a current requirement; extensibility is added only once a real need is confirmed.
- No overengineering: no design patterns or extra abstraction layers (interfaces, DI, wrappers) unless they remove duplication/complexity that exists now; no premature optimization — working and clear first, optimize only against a measured problem; no generic solution built for a single use case.
- Quality priority, highest to lowest: readability, directness (minimal indirection/magic), minimalism, consistency with existing project conventions. Prefer whichever option can be explained in one sentence.

<!--
Example:
- TypeScript files: kebab-case (e.g., `rate-limiter.ts`)
- Swift files: PascalCase (e.g., `SettingsView.swift`)
- Error responses: `{ success: false, error_code: 'CODE', message: '...' }`
- All time logic in PostgreSQL, never client-side
-->

## 7. Testing

<!-- Document your test commands and when to run them. -->

- Run only targeted tests for what you changed during development; run the full suite only before a release or when explicitly asked.

<!--
Example:
```bash
npm test              # All tests
npm run test:unit     # Unit tests only (~1s)
npm run test:e2e      # E2E tests (~20s, hits network)
```

**When to run which tests:**
| What changed | Run |
|---|---|
| Shared utilities | Unit tests |
| API endpoints | E2E tests |
| Database schema | Integration tests |
| Before deployment | All suites |
-->

## 8. Privacy & Security

<!-- Document non-negotiable security rules for your project. -->

<!--
Example:
- Audio/media NEVER stored — processed in memory, deleted immediately
- No user accounts — anonymous identity via device UUID
- Never log personal data or audio content
- Never reveal system internals (stack traces, DB schemas) in error messages
- Input validation on all external inputs
- RLS enabled on all database tables
-->
