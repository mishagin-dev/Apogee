---
name: merge
description: "Deprecated alias of /apogee:finish, kept for one release. Closes the current unit of work exactly as /apogee:finish does."
argument-hint: "(deprecated — use /apogee:finish)"
disable-model-invocation: true
---

# Merge (deprecated)

`/apogee:merge` was renamed to `/apogee:finish` in 4.0.0, which closes any unit of work opened by
`/apogee:start` (feature, bugfix, hotfix, research). This alias is removed in the next major
release.

Tell the user in one line that the command is now `/apogee:finish`, then do exactly what
`${CLAUDE_PLUGIN_ROOT}/skills/finish/SKILL.md` says, with these arguments: $ARGUMENTS
