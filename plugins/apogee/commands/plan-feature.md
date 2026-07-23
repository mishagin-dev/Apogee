# Plan Feature Command

Plan a feature with parallel research and a Gemini second opinion before exiting plan mode. Designed to run inside Plan Mode (toggle with Shift+Tab).

**Usage:** `/plan-feature [feature description]`

---

## Load context first

Always load core context before Phase 1 research starts — the same files `/prime` loads, sized
the same way `/prime` sizes them (a given task doesn't need "what's next" framing; planning with
nothing given does). Skipping this doesn't save work: Phase 1's Explore agents would just rescan
the codebase from scratch, unstructured, instead of starting from these three already-written docs.

1. `docs/apogee/ai-context/spec.md`
2. `docs/apogee/ai-context/project-structure.md`
3. `docs/apogee/ai-context/progress.md` — only if `$ARGUMENTS` is empty (no feature was specified).

If a doc is missing or still a scaffold stub (`apogee:scaffold-stub` sentinel), it isn't real
context — note it, suggest `/apogee:init`, and continue with whatever's real.

If `$ARGUMENTS` is empty after loading: propose the next feature from `progress.md`'s priorities
or known issues, and confirm it with the user before treating it as the feature to plan.

---

## Approach

For concerns not directly in front of you — a third-party API/SDK, a platform capability, a library version question, or a cross-cutting code search — dispatch sub-agents in parallel. Treat training data as potentially stale, especially for fast-moving platforms, SDKs, and APIs. Context7 MCP first; WebSearch only if Context7 lacks coverage. For a genuinely deep external unknown that ad-hoc WebSearch can't settle — a new third-party integration, an unfamiliar protocol, a compliance/regulatory requirement — escalate to the `deep-research` skill **if it's available**. It's the top rung of the ladder, not a default: skip it for routine, code-adjacent lookups.

For architecture decisions, state the tradeoff, not just the chosen option. For UI flows, plan how you'll verify the change end-to-end (manual browser test, simulator run, integration test — whatever applies). After implementing the code, but before final verification, run `/review-work` to catch bugs upfront.

Before exiting plan mode, invoke `/second-opinion` on the draft. You are the authority — Gemini's role is to flag blind spots or alternatives worth considering, not to overwrite your judgment. Note what you took vs rejected, then exit plan mode with the synthesized plan.

ultrathink

---

**Feature to plan:** $ARGUMENTS
