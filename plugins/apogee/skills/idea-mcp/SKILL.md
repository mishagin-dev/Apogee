---
name: idea-mcp
description: "Activate when the JetBrains/IntelliJ IDEA MCP server is connected (mcp__idea__* tools respond) and the task involves code intelligence in any supported language (PHP, Go, Rust, TypeScript, Kotlin, Java, Swift): symbol search, rename across references, checking file problems/inspections, build and compile errors, running IDE configurations, database introspection, framework introspection (Symfony/Doctrine/Twig for PHP), or interactive debugging. Mandates MCP tools over terminal equivalents. Triggers: 'find symbol', 'rename across references', 'check file problems', 'build errors', 'compile errors', 'run configuration', 'code intelligence', 'reformat file', 'inspections', 'database', 'symfony routes', 'doctrine entities', 'debug', 'set breakpoint'."
user_invocable: false
metadata:
  internal: true
  tier: rules
---

# JetBrains IDEA MCP — Tool Reference

## Activation & IDE Detection

This skill is **active only** while `mcp__idea__*` calls succeed. If the server
is unreachable (connection error), fall back to native tools silently.

**Detection ladder (strongest to weakest):**

1. `mcp__idea__*` tools appear in the session tool list — primary signal.
2. Any cheap MCP call returns data or the open-projects disambiguation error —
   either response confirms the server is running.
3. `echo $TERMINAL_EMULATOR` → `JetBrains-JediTerm` — only when Claude is
   launched from the IDE's own terminal.
4. `echo $__CFBundleIdentifier` → `com.jetbrains.*` (macOS) — same caveat.
5. `pgrep -fl 'phpstorm|idea|webstorm|goland|rustrover|clion'` — supplementary
   process-level check.

**Always pass `projectPath`** — without it the server returns a disambiguation
error listing all open projects. Use that list to pick the correct path.
The target project must be **open in the IDE** — MCP cannot see closed projects.

---

## Language Support

Semantic tools (`search_symbol`, `get_symbol_info`, `rename_refactoring`, etc.)
require the matching JetBrains language plugin and a fully indexed project.

**Indexed (verified):**
- PHP — IntelliJ/PhpStorm
- Kotlin / Java — via IntelliJ IDEA
- TypeScript / JavaScript — via built-in web support

**Not indexed / limited:**
- **Swift**: `KosmosVPN/Apple` opens as a generic `WEB_MODULE`.
  `search_symbol` returns no Swift symbols. → Use native **Read / Grep / Glob**
  for Swift code; `rename_refactoring` will not work. The enforcement hooks exclude
  this path automatically via `~/.claude/hooks/idea-enforce.json`.
- Any folder opened as `WEB_MODULE` with non-web code has the same limitation;
  call `get_project_modules` to verify the module type when in doubt.

**Go / Rust**: supported by GoLand/RustRover plugins when the project is open in
IntelliJ IDEA Ultimate. Verify with one `search_symbol` call before relying on
semantic tools.

---

## Code Intelligence

No terminal equivalent for semantic lookup. High profit when the project is indexed.

| Task | Tool |
|---|---|
| Find class / method / function / interface / struct by name | `search_symbol` — semantic index; returns file, line range, and full body excerpt |
| Get type, signature, inheritance chain, docs | `get_symbol_info` — pass file + 1-based line + column of the symbol reference |

---

## Build & Compile

Runs the IDE build system and returns structured errors. Works for Go, Rust,
Kotlin, TypeScript — any language with a JetBrains build integration.

| Task | Tool |
|---|---|
| Build the project / check for compile errors | `build_project` — returns structured errors with file + line + message |
| Check a single file for static analysis errors | `get_file_problems` — returns `{"errors":[]}` when clean |
| Check file with warnings + quick-fix IDs | `get_inspections` — superset; includes severity, line/col, fix family names |
| Apply an auto-fix | `apply_quick_fix` — pass `quick_fix_id` from `get_inspections` result |

---

## Refactoring & Formatting

IDE-backed refactoring updates all cross-language references atomically.

| Task | Tool |
|---|---|
| Rename symbol across all references | `rename_refactoring` — **mandatory for indexed languages**; updates all references including templates, config, and annotations |
| Apply IDE code style to a file | `reformat_file` |

> **Rule**: symbol renaming in indexed projects — always `rename_refactoring`,
> never `sed` or `replace_text_in_file`. After every file edit, call
> `get_inspections` to verify no new errors were introduced.

---

## Run Configurations

| Task | Tool |
|---|---|
| List all IDE run configurations | `get_run_configurations` — includes `supportsDynamicLaunchOverrides` flag per config |
| Discover runnable entry points in a file | `get_run_configurations(filePath=...)` — test methods and main entry points with line numbers |
| Run a configuration | `execute_run_configuration` — pass launch overrides **only** when `supportsDynamicLaunchOverrides=true` |

---

## Databases (conditional — only when a DB connection is configured)

| Task | Tool |
|---|---|
| List configured connections | `list_database_connections` |
| List schemas | `list_database_schemas` |
| Explore schema objects (tables, views, etc.) | `list_schema_objects`, `list_schema_object_kinds`, `get_database_object_description` |
| Preview table rows | `preview_table_data` |
| Execute a query | `execute_sql_query` — use `cancel_sql_query` if it runs long |
| See recent queries | `list_recent_sql_queries` |
| Verify connectivity | `test_database_connection` |

---

## PHP / Symfony (conditional — only for PHP projects)

IDE-indexed introspection — faster and richer than `bin/console` round-trips.

| Task | Tool |
|---|---|
| Search code by AST pattern | `search_structural` — SSR; pick a pattern from `get_structural_patterns` first; **always set `maxResults` ≤ 20 and `timeout` ≤ 8000 ms** |
| List PHP SSR pattern templates | `get_structural_patterns` — 23 categorized templates |
| Find route by name or URL fragment | `list_symfony_routes_url_controllers` — `urlPath` is a **substring match** of the path pattern |
| Find service in the DI container | `locate_symfony_service` — pass FQN or service ID |
| Generate a service definition scaffold | `generate_symfony_service_definition` |
| List Doctrine entities | `list_doctrine_entities` — includes services/VOs/enums — filter results |
| Get entity fields, column names, types, relations | `list_doctrine_entity_fields` — pass exact FQN |
| List console commands | `list_symfony_commands` — use `fileGlob: src/**` for project-only |
| List Twig filters / functions / tags / tests | `list_twig_extensions` |
| List Twig template variables with PHP types | `list_twig_template_variables` |
| Find where a template is used | `list_twig_template_usages` |
| List Symfony UX Twig components | `list_twig_components` |
| Debug FormType options | `list_symfony_forms`, `list_symfony_form_options` |
| Trace recent HTTP requests | `list_profiler_requests` — requires profiler enabled + dev server running |
| Get PHP project config | `get_php_project_config` |
| List Composer dependencies | `get_composer_dependencies` |

> **Rule**: Symfony context (routes, services, entities) — always via MCP,
> never parse YAML/XML manually or run `bin/console` for introspection.

---

## Debugging (conditional — PHP / Xdebug only)

Interactive step-debugging with no terminal equivalent.

```
1. xdebug_list_breakpoints                        — review existing breakpoints
2. xdebug_set_breakpoint(file, line)              — set a line breakpoint
3. xdebug_get_debugger_status                     — confirm no active session
4. xdebug_start_debugger_session                  — launch via configurationName
                                                    OR filePath + line
   [wait for breakpoint hit → session paused]
5. xdebug_get_stack                               — call stack at pause point
6. xdebug_get_frame_values(frameIndex, depth=1)   — locals in frame
7. xdebug_evaluate_expression(expression)         — eval PHP in current scope
8. xdebug_step_over / xdebug_step_into / xdebug_step_out
9. xdebug_control_session(action=RESUME)          — continue to next breakpoint
10. xdebug_stop                                   — end session
```

> A PHP-specific alternative family also exists: `xdebug_status`,
> `xdebug_request`, `xdebug_context`, `xdebug_eval`, `xdebug_stack` — same
> stepping tools, different session initiation. Use the IDE-debugger family above
> by default.

---

## Use Native Tools Instead

These MCP tools are disabled or should not be used — native Claude Code tools are
faster, IDE-independent, and routed through the correct hook/permission system:

| MCP tool | Use instead |
|---|---|
| `read_file`, `get_file_text_by_path` | **Read** tool |
| `create_new_file` | **Write** tool |
| `replace_text_in_file` | **Edit** tool |
| `search_file`, `find_files_by_glob`, `find_files_by_name_keyword` | **Glob** tool |
| `search_text`, `search_regex`, `search_in_files_by_text`, `search_in_files_by_regex` | **Grep** tool |
| `list_directory_tree` | `Bash(ls -R)` / `Bash(tree)` |
| `execute_terminal_command` | **Bash** tool |
| `get_all_open_file_paths`, `open_file_in_editor` | not needed in agentic context |
| `get_project_dependencies` | Read `composer.json` / `go.mod` / `Cargo.toml` directly |

---

## Priority Rules

```
Symbol search:    search_symbol              > Grep / rg / grep
Symbol rename:    rename_refactoring         > sed / replace_text_in_file
File errors:      get_inspections            > static analysis CLIs
Build errors:     build_project              > terminal build commands
After every edit: get_inspections            (always verify)
Run tests/app:    execute_run_configuration  > bare terminal commands
Reformat:         reformat_file              > manual edits / formatters
File read:        Read tool                  > read_file / get_file_text_by_path
File search:      Glob tool                  > find_files_by_glob / search_file
Text search:      Grep tool                  > search_in_files_by_text / search_text
Symfony context:  list_symfony_* / locate_* > bin/console introspection  (PHP only)
Debugging:        xdebug_* IDE tools         > var_dump / dd() / Xdebug CLI  (PHP only)
```

## Context economy (this skill replaces an LSP-enforcement kit)

The whole point is to spend fewer tokens: precise IDE queries instead of "grep + read
the whole file." Two habits the enforcement hooks back:

- **Navigate before bulk-reading.** To understand a symbol, call `search_symbol` /
  `get_symbol_info` (and `get_file_problems` for diagnostics) to get the exact file +
  line range, then `Read` only that range (`offset`/`limit`). Reading whole code files
  blind is the expensive default this skill exists to avoid. (`idea-read-gate.py` enforces
  this once idea-first mode is active: full-file code reads are budgeted; an idea call
  refreshes the budget; surgical `offset`/`limit` reads are always free.)
- **Subagents have no idea-MCP.** A delegated "grep/find this symbol" task runs grep +
  whole-file reads inside the subagent — the exact waste we avoid. Resolve symbols/locations
  HERE first, then pass concrete `file:line` context into the subagent prompt. (`idea-agent-guard.py`
  blocks raw code-search delegation while idea-first mode is active.)

Activation (fail-closed / forced): in a JetBrains project (a `.idea/` dir) with the IDE running,
`idea-force-activate.py` (SessionStart) turns the guards ON from turn 1 — native symbol search and
blind full-file code reads are blocked immediately, so you MUST use idea. Make any `mcp__idea__*`
call to proceed (the matcher is `mcp__idea__.*`, so ANY tool counts — `search_symbol`,
`get_all_open_file_paths`, `list_directory_tree`, …); pass `projectPath` if asked which project. The
first success "confirms" the mode (`idea-usage-tracker.py`). This is not a trap: if idea is forced on
but genuinely unreachable (e.g. Claude launched outside the IDE), the block SELF-HEALS after a couple
of attempts and native tools resume. Any idea error/disambiguation also deactivates → native. Global
escape `IDEA_GATE_OFF=1`; per-project opt-out via `~/.claude/hooks/idea-enforce.json`.

---

## Gotchas

- **Always pass `projectPath`** — omitting it returns an open-projects list;
  use that list to confirm the correct path.
- **`search_structural` times out on large codebases** — always set
  `maxResults` ≤ 20 and `timeout` ≤ 8000; PHP-only tool.
- **`list_doctrine_entities` includes non-entities** — domain services, value
  objects, and enums appear alongside `@ORM\Entity` classes; verify with
  `get_symbol_info` when in doubt.
- **`list_symfony_routes_url_controllers` urlPath is a plain substring match**
  — use `routeName` filter for precision.
- **`list_profiler_requests` requires a live profiler** — unavailable in
  test/prod environments.
- **`xdebug_start_debugger_session` launch overrides are gated** — pass
  `programArguments`/`workingDirectory`/`envs` only when `get_run_configurations`
  reports `supportsDynamicLaunchOverrides=true` for that config.
- **Swift not indexed**: `search_symbol` and `rename_refactoring` are ineffective
  for `.swift` files in the current setup — the Apple project opens as `WEB_MODULE`.
  Use native tools. Enforcement hooks exclude this path via `idea-enforce.json`.
