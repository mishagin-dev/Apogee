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
├── .claude/
│   ├── commands/
│   │   ├── prime.md                    # /prime — load core project context
│   │   └── merge.md                    # /merge — finalize worktree work
│   ├── hooks/
│   │   ├── review-on-stop.sh           # Advisory review nudge on stop
│   │   ├── snapshot-baseline.sh        # Session baseline capture
│   │   ├── security-scan.sh            # MCP/plugin sensitive data scanner
│   │   ├── notify.sh                   # Audio notifications
│   │   ├── config/
│   │   │   ├── pipeline.json           # Review-on-stop configuration
│   │   │   └── sensitive-patterns.json # Security scan patterns
│   │   └── sounds/
│   │       ├── complete.wav
│   │       └── input-needed.wav
│   ├── skills/                         # Project-specific skills
│   └── settings.local.json             # Permissions, hooks, plugins
│
├── assets/                             # Visual assets (processed + source)
│   ├── app-icon/                       # App icons
│   ├── character/                      # Character/mascot art
│   ├── logo/                           # Brand marks and avatars
│   ├── social/                         # Social media graphics
│   └── web/                            # Website graphics (favicon, OG image)
��
├── docs/
│   └── apogee/                         # Apogee working memory (git-excluded, local-only)
│       ├── ai-context/                 # Core AI development context
│       │   ├── spec.md                 # What the product does
│       │   ├── project-structure.md    # THIS FILE — file tree and tech stack
│       │   ├── progress.md             # What's done, what's next
│       │   └── deployment-infrastructure.md # Hosting, accounts, CI/CD
│       ├── legal/                      # Privacy policy, ToS, compliance
│       ├── business/                   # Business plans, competitive analysis
│       ├── design-brand/               # Brand voice, design system, guidelines
│       └── open-issues/                # Active investigations and decisions
│
├── CLAUDE.md                           # AI development rules and standards
├── GEMINI.md                           # agy second-opinion consultant instructions
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
