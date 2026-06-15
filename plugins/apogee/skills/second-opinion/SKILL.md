---
name: second-opinion
description: Get an independent second opinion from another AI model via the locally installed `agy` CLI (antigravity-cli — defaults to a Gemini Pro model, can route to Gemini/GPT/Claude). Use this skill in Plan Mode for large or critical tasks, when stuck on a debugging dead end, when weighing architecture trade-offs, for subtle edge cases in code review, or whenever an independent perspective would add value. Also use it whenever the user explicitly asks for a "second opinion", "ask agy", "another perspective", "cross-check this", or "вторая точка зрения" — even if they don't name the tool. This is the successor to the gemini-based `second-opinion` skill (gemini-cli is being deprecated); prefer `agy` and fall back to `second-opinion` only if `agy` is unavailable.
---

# Second Opinion via agy

Get an independent second opinion from a different model family via the locally installed `agy` CLI (antigravity-cli). A genuinely different architecture and training makes it useful for catching blind spots, validating reasoning on edge cases, or surfacing trade-offs you might miss.

`agy` has full read access to the project — it can read files, grep code, and explore the codebase. You provide the specific question and any focused context; `agy` handles the rest.

## When to Use

- Architecture decisions with real trade-offs
- Debugging where you've been going in circles
- Code review on tricky logic or subtle edge cases
- Validating your reasoning before the user acts on it
- When the user explicitly asks for a second opinion

Don't use this for routine tasks — every call takes 30-90 seconds and has capacity limits. Reserve it for decisions where being wrong has real consequences.

## Model selection

Pinned to `Gemini 3.1 Pro (Low)` — a fast Pro-tier model. The model name is a human-readable string (NOT an API id), so it must be quoted: `--model "Gemini 3.1 Pro (Low)"`. `agy models` lists what's installed; a non-Claude model keeps the opinion independent from this Claude session. `Gemini 3.1 Pro (High)` is much slower — only worth it for an unusually deep review (raise the timeout if you switch).

Do **not** fall back to a smaller/weaker model when the pinned one is unavailable. Report unavailability and continue with Claude-only analysis.

## Process

### Step 1: Prepare the Prompt

`agy` has NO access to your conversation history, but it CAN read project files. Structure your prompt as:

1. **The question** — what exactly you want `agy` to weigh in on
2. **Your current thinking** (recommended) — share your position so `agy` can challenge it
3. **Specific context** (if needed) — pipe code snippets or diffs via stdin when the relevant code is scattered or you want to focus attention on specific sections

For questions about existing project code, you can simply reference file paths — `agy` will read them itself. Write the prompt in **English** (a global hook treats external-AI handoffs as English-only).

### Step 2: Invoke agy

**CRITICAL: Permission-free invocation pattern.** The command MUST start with `agy` (matches the `Bash(agy:*)` allow rule) and MUST NOT use `$()` command substitution or `/tmp/` file redirects — both trigger permission prompts. Run it in the **foreground** — a backgrounded `agy -p` never flushes its output.

**Standard call** (agy reads project files itself — preferred):

```bash
agy --model "Gemini 3.1 Pro (Low)" --dangerously-skip-permissions -p '<your question here>' 2>&1 | grep -viE '^(Warning|Loading|Registering|Scheduling|Data collection|Flushing|\[dotenv|True color)'
```

**With context piped via stdin** (for code snippets, diffs, or focused excerpts — use when context is scattered or you want to focus attention on specific sections):

```bash
agy --model "Gemini 3.1 Pro (Low)" --dangerously-skip-permissions -p '<your question here>' 2>&1 <<'CONTEXT_EOF'
<relevant code, diff, or context here>
CONTEXT_EOF
```

The Bash tool captures all output directly — no file redirects needed. The `grep -viE` filter drops `agy`'s startup noise (Loading, Registering, Scheduling, etc.).

**Reading the answer.** `agy` usually prints the answer to stdout. For a long answer it may instead print a short summary plus a `file://` link to a file like `~/.gemini/antigravity-cli/brain/<id>/<name>.md` — that file holds the full response, so read it.

**Required flags — no exceptions:**

| Flag | Why |
|------|-----|
| `--model "Gemini 3.1 Pro (Low)"` | Pro-tier model; quoted because the name has spaces/parens |
| `--dangerously-skip-permissions` | Without it `agy -p` HANGS on a tool-approval prompt nobody can answer headless |
| `-p` | Non-interactive headless mode |

**DO NOT use:**
- `$()` command substitution — triggers a permission prompt
- `/tmp/` file redirects — triggers a permission prompt
- `run_in_background` — `agy -p` never flushes its output when backgrounded

Set a **600-second timeout** on the Bash tool call (`agy` may need time to read files and reason; its own `--print-timeout` is 5m).

### Step 2b: Multi-Turn Discussion (Autonomous)

When the topic warrants debate (architecture, design reviews, trade-off analysis), **run the full multi-turn conversation autonomously** — do NOT ask the user for permission between rounds. Push back on `agy`'s points, let it push back on yours, iterate until you reach consensus or clearly identify the disagreements. Typically 2-4 rounds.

Continue the same conversation instead of starting fresh, in the foreground, prompt in English:

```bash
agy -c --dangerously-skip-permissions -p '<your English follow-up>' 2>&1 | grep -viE '^(Warning|Loading|Registering|Scheduling|Data collection|Flushing|\[dotenv|True color)'
```

`-c` (`--continue`) resumes the most recent conversation. If other `agy` sessions may run concurrently, capture the conversation id from the first call and resume that exact one with `--conversation <id>` instead. Run rounds **sequentially** — never launch parallel `agy` calls.

**When to use multi-turn:**
- Design reviews or architecture discussions — run the full debate autonomously
- `agy`'s answer is vague — ask it to be specific about the part that matters
- You want to challenge its reasoning — push back and see if it holds
- The question naturally has layers — e.g., "which approach?" then "what are the migration risks of that one?"

**When NOT to use multi-turn:**
- The first answer was clear and complete — just present it
- You're asking an unrelated question — start a fresh call (omit `-c`)

### Step 3: Present the Result

**If multi-turn:** Present a consolidated synthesis — the key agreements, remaining disagreements, and your joint recommendation. Don't dump each round's raw output; the user wants the conclusion, not the transcript.

**If single-turn:** Present `agy`'s response, then add your own brief synthesis: where you agree, where you disagree, and what the user should take away from both perspectives. The value is in the synthesis, not just the raw second opinion.

**If `agy` is unavailable** — it hangs past the timeout, returns nothing, errors, or isn't installed: report that plainly and continue with your own analysis. Do NOT silently fall back to a weaker model — a weak second opinion isn't worth the false confidence it creates. You may retry once with a faster model (e.g. `"Gemini 3.5 Flash (High)"`), or use the gemini-based `second-opinion` skill if `agy` itself is broken. Tell the user which path you took.

## Important Rules

1. **Never fall back to a lesser model.** A Pro-tier model or nothing — a weaker model's opinion isn't worth the false confidence it creates.
2. **Don't over-use.** This is for genuinely tricky decisions, not routine coding questions you can answer confidently yourself.
3. **Shell quoting matters.** For prompts containing single quotes, escape with `'\''`. For complex prompts, use the stdin heredoc.
4. **Command must start with `agy`** (matches `Bash(agy:*)`), run in the foreground, with `--dangerously-skip-permissions`. Never wrap in `$()` or redirect to `/tmp/`.
