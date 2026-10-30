---
name: research
description: "The research unit of work: opens a dated note in docs/apogee/research/, answers the question into it with deep reasoning and an independent second opinion from agy, and closes it once the conclusion holds. Called by /apogee:start research (open) and /apogee:finish on a research note (close); not for code changes."
argument-hint: "open <question or slug> | close [<note path or slug>]"
effort: xhigh
user-invocable: false
---

# Research

ultrathink. A research item answers a question the project has to decide on, so the answer is
worth the deepest reasoning available: weigh the evidence, look for what would prove the draft
wrong, and only then conclude. This skill holds the whole research procedure; `/apogee:start
research` and `/apogee:finish` hand over to it, so the extended reasoning applies to research and
not to every branch opened.

No branch, no git: the note lives in `docs/apogee/research/`, which is local-only (a ceremony-free
deliverable, RULES.md "Files"). Code is not changed under a research item; if the answer calls for
code, the close proposes the follow-up `start`.

**Context:** $ARGUMENTS

---

## Open

### 1. The note

Create `docs/apogee/research/<YYYY-MM-DD>-<slug>.md` (slug: lowercase, words joined by `-`, at
most 40 characters) with this skeleton, filled from the request:

```markdown
---
status: open
started: <YYYY-MM-DD>
question: "<the question, one sentence>"
---

# <Title>

## Question
## Context            <!-- why it is asked now, constraints, what is already decided -->
## Findings           <!-- evidence, each claim with its source -->
## Options            <!-- when there is a choice: trade-offs, not a survey -->
## Second opinion     <!-- agy's challenge of the draft and how each point was resolved -->
## Conclusion         <!-- the answer, and what it means for the project -->
## Sources
```

Add one line to `docs/apogee/README.md`'s Index: path, the question, `(open)`.

### 2. Tracker (beads projects only)

Skip when there is no `.beads/` at the repo root. One issue, no epic:
`br create "<question>" -t task -l research --json`, its `external_ref` set to the note's path;
claim it (`br update <id> --claim --actor "${BR_ACTOR:-assistant}"`) and log
`br comments add <id> --message "start: opened <note path>"`.

### 3. Research into the note, not into the chat

1. **Context.** Restate the question, the constraints, and what is already decided (ADRs, the
   project's `CLAUDE.md`).
2. **Findings.** Gather evidence and write each claim with its source: Context7 for library and
   API questions, WebSearch for the rest, the codebase itself for how things are now. Prefer
   primary sources; date anything that changes over time.
3. **Options.** When there is a choice, the trade-offs of each, not a survey.
4. **Draft the conclusion**, but do not write it into Conclusion yet.

### 4. Second opinion (required)

Invoke `apogee:second-opinion` with the question, the key findings with their sources, the
options, and the draft conclusion, and ask `agy` to challenge it: facts it believes are wrong,
options that are missing, a conclusion it would reach instead. Send a focused, redacted excerpt;
never point `agy` at secret files (the second-opinion skill's Step 1 rule).

Record the result under **Second opinion**: the model, its verdict (agrees / disputes / adds), and
each point with how it was resolved: accepted (what changed in the note) or rejected (why, with
evidence). Where `agy` contradicts a finding, check a source before resolving; neither model's
word settles a fact.

If `agy` is unavailable (not installed, model unavailable, capacity), write
`Unavailable: <reason>` under the heading and continue; do not substitute a weaker model.

### 5. Conclude

Write **Conclusion**: the answer, what it means for the project, how confident it is, and what
evidence would change it. Report to the user in a few lines: the answer, where `agy` disagreed and
how that was resolved, and the next step.

---

## Close

Called by `/apogee:finish` with the note (or the only open one).

1. **Completeness.** The note must have a non-empty **Conclusion**, **Sources** (or an explicit
   "no external sources" with the reason) and **Second opinion** (the recorded challenge, or
   `Unavailable: <reason>`). Conclusion or Sources missing → finish the research first; don't
   mark an unanswered question done. Second opinion missing → run Open step 4 now, revise the
   conclusion if it changes, then continue.
2. **Close it.** Frontmatter `status: done` plus `finished: <YYYY-MM-DD>`; in
   `docs/apogee/README.md` change the Index line's `(open)` to the one-line answer.
3. **Promote what lasts.** A conclusion that is a standing fact about the domain belongs in
   `docs/apogee/domain/`; a settled architectural choice belongs in `CLAUDE.md` §4 (or an ADR in
   the project). Move or link it; the research note stays as the record of how it was decided.
4. **Tracker** (beads): close the research issue with the conclusion as the reason.
5. **Follow-up.** If the conclusion calls for code, end the report with the exact next command,
   e.g. `/apogee:start feature <slug>`; don't start it unasked.

No git anywhere in this skill: `docs/apogee/` is local-only.
