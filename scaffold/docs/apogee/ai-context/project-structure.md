<!-- apogee:scaffold-stub: replace with real project context via /apogee:init -->

# Project Structure

<!-- This file documents the file tree, tech stack, and directory organization.
     Update after adding new files/directories or changing dependencies. -->

## Technology Stack

<!-- List your actual technologies. Remove or add rows as needed. -->

| Layer | Technology | Notes |
|-------|-----------|-------|
| Frontend | | |
| Backend | | |
| Database | | |
| AI/ML | | |
| Hosting | | |
| CI/CD | | |

## File Tree

```
your-project/
├── .claude/                            # local-only (git-excluded): settings.local.json, plans/, memory/
├── .beads/                             # br issue tracker (local-only, git-excluded)
├── docs/
│   └── apogee/                         # Apogee working memory (local-only, git-excluded)
│       └── ai-context/                 # Core AI development context
│           ├── spec.md                 # What the product does
│           ├── project-structure.md    # THIS FILE: file tree and tech stack
│           ├── progress.md             # What's done, what's next
│           └── deployment-infrastructure.md # Hosting, accounts, CI/CD
│
├── CLAUDE.md                           # AI development rules (local-only, git-excluded)
├── GEMINI.md                           # agy second-opinion consultant instructions (local-only)
│
├── src/                                # Your source code directories go here
```

## Directory Conventions

<!-- Document your naming and organization patterns. -->

<!--
Example:
- Source code in `src/` with feature-based organization
- Tests colocated next to source files as `*.test.ts`
- Shared utilities in `src/shared/`
- Each feature directory is self-contained (routes, models, services)
-->
