# ADR 0005 — Enforcement reduced to safety-only; the rest of the machinery becomes context

**Status:** Accepted · **Date:** 2026-07-29

## Context

Apogee shipped thirteen blocking hooks: five idea-mcp guards, two `br` edit/branch gates, two Stop
gates (review→docs and br-progress), the git-commit `-F` enforcer, a six-rule git-flow enforcer, and
a language guard on external-AI calls. [ADR 0002](0002-plugin-not-global-hooks.md) describes this
machinery as *gates*, on the premise that a rule the agent can ignore is a rule that will be ignored.

A three-part audit conducted 2026-07-29 does not support that premise.

**The blocking layer defends almost nothing irreversible.** Of ~2,900 lines of blocking machinery,
exactly one gate guards an outcome that cannot be undone — `core/security-scan.sh`, because a secret
sent to an external MCP server cannot be unsent. Every other gate protects against something
recoverable with a single command: `git reset --soft HEAD~1`, `br update <id>`, `git branch -m`, or
"run the skill next session."

**The real safety net was never these hooks.** `permissions.deny` — written by `setup.sh` into every
project and enforced by Claude Code itself, entirely independent of this plugin — already blocks
`sudo`, every `rm -rf` spelling, `git push --force`, `git reset --hard`, `git clean -f`,
`git restore .`, and `git branch -D`. Those are the genuinely destructive actions. The hooks enforce
workflow tidiness.

**Eleven of thirteen blocking gates duplicate rules already written as prose.**
`skills/git-flow/SKILL.md` literally reprints the hook's own six-rule list; the `-F` commit rule
appears three times in `skills/git-commit/SKILL.md`. The instruction layer and the enforcement layer
are the same content written twice.

**The `idea/` group — the largest bracket at 1,317 lines — blocks read-only operations.** All five
guards deny `Grep`/`Glob`/`Read`/delegation to save tokens. Nothing is written, nothing destroyed;
the worst outcome prevented is a larger context window. It is also the only fail-*closed* group,
force-activated at SessionStart on an unproven MCP connection, which is why it needs a self-heal
counter, subagent carve-outs, and a per-project opt-out just to be safe to ship. `IDEA_GATE_OFF`
does not work in three of the five.

**The record shows cost without demonstrated benefit.** Eleven distinct false-positive defects (one
still open — the `^{commit}` rev-syntax match); the submodule "umbrella branch" trap took three
releases across seventeen days to close, each fix shipping a fresh hole; six separate anti-deadlock
mechanisms exist solely to stop gates trapping a session; roughly half of all releases were spent
repairing the gates rather than shipping capability. Most tellingly, **four gates ran as silent
no-ops for their entire lifetime** — `br-progress-gate.sh` read a config path that never existed,
`br-branch-gate` Rule B called an undefined function swallowed by a bare `except` — and no incident
was observed while they were broken.

The one caveat worth stating: the audit found no changelog entry crediting a gate with catching a
real mistake, but nobody records "the gate worked today," so that absence is weak evidence on its
own. The conclusion does not rest on it. It rests on the gates that were provably inert for months
with no consequence, and on the cost side, which is documented in detail.

**The documentation instructs developers to switch the gates off.** `docs/INSTALL.md` prescribes
`BR_GATE_OFF=1 REVIEW_GATE_OFF=1 IDEA_GATE_OFF=1 TOOL_LANG_OFF=1`, verbatim, "for friction-free
development," and `CLAUDE.md` keeps this repo free of `.beads/` specifically so the heaviest bracket
stays inert. The enforcement layer is designed so its author does not have to live under it.

**The complexity was self-inflicted.** A parallel DRY audit found eight significant duplications —
four hand-copied `.beads/` walk-up loops, a third divergent code-extension list, two divergent
exempt-directory sets, two Stop gates with a documented ping-pong history. Every one of them exists
to serve the enforcement layer, and every one disappears when it does. `core/lib/gate_common.py` and
`core/lib/file_patterns.sh` exist only to keep gates from contradicting each other.

Three things survive the audit:

1. **`core/security-scan.sh`** — the only gate defending an irreversible outcome. It is also
   currently dead code: it inspects `.code_context`, `.problem_description`, and `.attached_files[]`,
   the schema of a deprecated gemini MCP server no longer configured anywhere.
2. **The git-flow `release`/`hotfix finish` ASK** — guards the production branch and a tag, costs one
   regex, and is already an ASK rather than a DENY.
3. **The open-children check on autonomous `finish`** — see the Decision below. This one required
   refining the criterion.

## Decision

**Reduce the blocking surface to two hooks and three rules, keep the entire context layer, and move
the one orphaned rule into prose.**

1. **Keep `core/security-scan.sh`**, rebuilt (see below). The only DENY on the MCP surface.
2. **Keep `enforce-git-flow-skill.py` Rule 1** — the ASK on `git flow release|hotfix finish`.
3. **Keep Rule 2b, narrowed to `APOGEE_RUN_PLAN=1`-tagged commands only.** The draft of this ADR
   deleted it, replacing it with a self-check inside `/apogee:run-plan`'s own loop. That was wrong,
   and a second-opinion review caught it: **prose instructions rely on a human backstop that an
   unattended loop does not have.** A model drifting over a long autonomous run will eventually
   believe an epic is complete, close it, merge, and proceed — compounding across epics. The audit
   rated this failure TRIVIAL ("tracker bookkeeping"), but that rating assumes supervision; unwinding
   several branches merged on a false premise is not trivial.

   This refines the cut criterion rather than abandoning it: the test is not only *"is the outcome
   irreversible"* but also *"is a human present to catch it."* Untagged interactive finishes now get
   no check at all — simpler than the previous fail-open behavior. Tagged autonomous finishes get the
   check, fail-closed.
4. **Delete every other blocking hook**: the five idea guards plus `idea-force-activate.py`,
   `idea-usage-tracker.py`, and `lib/idea_symbols.py`; `br-edit-gate.py`; `br-branch-gate.py`; both
   Stop gates; the git-commit enforcer; the language guard; and git-flow Rules 3, 4, 5, and 6.
5. **Delete the passive hooks that existed only to feed a deleted gate**: `snapshot-baseline.sh` and
   its `gated.sh` wrapper, `br-snapshot.sh`, `br-sig.py`, `track-file-touch.sh`, and
   `skill-run-tracker.py`. With their consumers gone, `core/lib/` has no cross-group users left and is
   dissolved — the still-used helpers move into the group that uses them.
6. **Keep the entire context layer intact**: `apogee-session-start.py`, `br-prime.sh`,
   `br-capture-gate.py`, `idea-nudge.py`, `unfinished-branch-nudge.py`, `notify.sh`,
   `cleanup-session.sh` — plus every skill and every command. Nothing that makes the agent better
   informed is removed.
7. **Move exactly one rule into prose.** Deleting a hook must not delete its rule — but relocating
   *all* of them would bloat the context window and degrade adherence to everything, which is the
   same mistake in a new place. Only the `br`-tracking rule exists nowhere but hook code; it is
   written into `scaffold/CLAUDE.md` §1 and cross-referenced from root `CLAUDE.md`. The git-flow
   discipline, the `-F` commit rule, the review→docs habit, and the idea-mcp preference are all
   already stated in prose and are left exactly as they are.

**The rebuilt `security-scan.sh`** scans the whole `tool_input` rather than enumerated per-server
fields — field enumeration is precisely what rotted — but extracts values line-by-line via
`jq -r '..|strings'` with a size cap, because a large minified payload collapsed into one line would
choke `grep`. It matches **high-confidence patterns only**: vendor-prefixed tokens, PEM private-key
blocks, and credential-bearing connection strings. The generic heuristics are deleted:
`password\s*[:=]` matches `password: str` in a Python signature and `API_KEY=os.environ[...]` in any
`.env.example`, and the 24-entry exact-string whitelist was an unwinnable arms race against them.
This trades recall for precision deliberately — a scanner that cries wolf gets switched off, and a
switched-off scanner has zero recall in practice, which the four escape envs already demonstrate.

## Consequences

- **A careless agent can now do what the deleted gates prevented**: edit code with no `br` step, end
  a session with untracked work, skip `/apogee:review-work`, `git commit -m` ad hoc, hand-roll a
  merge, commit on a base branch. This is accepted. Each is recoverable, visible in
  `git status`/`git log`, and stated as a rule the agent reads.
- **The escape environment variables lose their targets and leave the documentation**:
  `BR_GATE_OFF`, `REVIEW_GATE_OFF`, `IDEA_GATE_OFF`, `TOOL_LANG_OFF`, and the per-project
  `~/.claude/hooks/idea-enforce.json` opt-out. There is nothing left to escape from; developing
  inside a `.beads/` + git-flow project no longer requires any opt-out.
- **`pipeline.json` shrinks to `run_plan` only.** `enabled`, `min_lines_changed`, `review_threshold`,
  `file_patterns`, `review_command`, `docs_command`, `phases`, and the top-level `test_command` lose
  their last consumers.
- **The "one source of truth for what counts as a code file" invariant is retired, not relocated** —
  all three of its consumers are gone, so the rule in `CLAUDE.md` is deleted rather than updated.
- **The secret scanner will miss exotic, unprefixed credentials.** Accepted, for the reason above.
- **This is a breaking change to a marketplace-distributed plugin.** Documented behavior and
  documented configuration are removed; a user with `REVIEW_GATE_OFF=1` set, or a tuned
  `review_threshold`, gets silence rather than an error. It ships as a major version bump.
- **The hook surface drops from 27 wired commands to 10**, roughly 2,700 lines of hook code are
  deleted, and the shared-library layer that existed to keep gates consistent with each other goes to
  zero.

## Relationship to earlier ADRs

- **ADR 0002 stands.** The plugin/scaffold/preferences split, self-gating, and the bundled-skills
  amendment are unaffected. Only the *characterization* changes: what 0002 calls "gates" is now, with
  two exceptions, context injection. Its Context section is a historical record and is not rewritten.
- **ADR 0003 is partially superseded** and carries a dated amendment. Its Decision §2 said to keep the
  `idea/` group "exactly as they are" pending a confirmed JetBrains → Zed migration. That is
  overridden here on different grounds — not IDE migration, but the finding that the guards block
  read-only work for token economy. The `apogee:idea-mcp` skill, the `mcp__idea__*` baseline
  permissions, the scaffold's "idea-mcp first" rule, and `idea-nudge.py` all remain; 0003's retirement
  trigger and its Steps 4-8 stand unexecuted.
- **ADR 0001 and 0004 are unaffected.** `br` remains the tracker — now recorded as memory rather than
  enforced as ceremony.

## Revisit triggers

Re-open this decision if, across a meaningful sample of real sessions, any of these is observed more
than incidentally: work reaching a merge with no `br` record; `/apogee:review-work` skipped before a
release; commits landing on `main`/`develop`; or a secret reaching an MCP server that the rebuilt
scanner missed. The answer would not be to restore the deleted gates wholesale — it would be to gate
the single behavior that actually failed.
