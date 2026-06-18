# Documentation Validation Rules

Validate human-facing docs against the code. The goal is honesty: a doc that claims something the code
no longer does is worse than no doc.

## What to check

| Check | How | Severity |
|-------|-----|----------|
| Referenced symbols exist | Every function/type/endpoint named in a doc resolves to a real source symbol | CRITICAL |
| Examples match signatures | Code samples call the current signature (arg names, order, types) | CRITICAL |
| Internal links resolve | Every relative `.md` link points to an existing file/anchor | CRITICAL |
| Required sections present | A reference doc has Overview + Usage (or an explicit reason it doesn't) | MEDIUM |
| No stale claims | "as of <date>" / "Status: X" lines are recent and still true | MEDIUM |
| No hardcoded local paths | No `/Users/...`, `/home/...` absolute paths in committed docs | LOW |

## Signpost rules

- **No line numbers.** Reference functions, types, and files by semantic name — line numbers rot on the
  next edit.
- **References must exist.** A signpost that points at a renamed/removed symbol is a CRITICAL failure.
- **Use real names.** `authenticate()`, `UserService` — not "the auth function".

## Validation report (inline)

Report findings to the user directly; do not write a machine report file. Group by severity and give the
exact location:

```
CRITICAL: Broken references (2)
   docs/auth.md -> login_user() (renamed to authenticate())
CRITICAL: Broken links (1)
   docs/index.md -> missing.md (not found)
MEDIUM: Stale claims (1)
   docs/code-map.md -> "as of 2024-01" (8 months old)
```

## Anti-patterns

| DON'T | DO INSTEAD |
|-------|------------|
| Sample a few files and declare the docs "healthy" | Check every referenced symbol/link |
| Say "looks fine" while links are broken | Report exact counts and locations |
| Rewrite human-authored prose to "fix" it | Flag it; let the author decide |
| Reference symbols by line number | Use semantic names |
| Duplicate authoritative content across docs | Link to one source of truth |
