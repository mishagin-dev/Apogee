# Documentation Generation Templates

Human-readable templates. Keep them lean — fill only the sections a reader needs; drop the rest.

## Feature / API Reference

```markdown
---
title: "[Feature Name]"
sources: [path/to/main.ext]
last_updated: YYYY-MM-DD
---

# [Feature Name]

## Overview

[2-3 sentences: what this feature does and when to reach for it.]

## Usage

[The shortest runnable example that shows it working.]

## API

| Symbol | Signature | Description |
|--------|-----------|-------------|
| `funcName` | `funcName(arg: Type) -> Ret` | What it does |

For each public symbol that needs detail:

### `symbolName`

**Purpose:** [one line]
**Parameters:** `param` (type) — description
**Returns:** [what it returns]
**Notes:** [non-obvious caveats, errors thrown]

## Related

- [Link to neighbouring docs]
```

## Code-Map (architecture overview)

```markdown
---
title: "Code Map"
last_updated: YYYY-MM-DD
---

# Code Map: [Project]

## Overview

[2-3 sentences on the system's shape and purpose.]

## Directory Structure

```
src/
├── module1/     # purpose
├── module2/     # purpose
└── utils/       # shared helpers
```

## Key Components

### [Module]
- **Purpose:** what it does
- **Entry point:** `semanticName` (no line numbers)
- **Key files:** `handler.ext`, `models.ext`

## Data Flow

[How a request / the main workflow moves through the system. ASCII arrows are fine.]

## External Dependencies

[Notable third-party libraries/services and why they're used.]
```

## Stub (for a discovered-but-undocumented feature)

```markdown
---
title: "[Feature Name]"
status: STUB
created: YYYY-MM-DD
sources: [detected source files]
---

# [Feature Name]

> AUTO-GENERATED STUB — replace with real content.

## Overview

[Brief description of this feature.]

## Sources

- `path/to/source.ext`

## API

| Symbol | Signature | Description |
|--------|-----------|-------------|
```

## Section Markers

Use markers so regeneration never clobbers human prose:

```markdown
<!-- HUMAN-MAINTAINED: do not auto-generate -->
[preserved during updates]

<!-- AUTO-GENERATED: safe to replace -->
[regenerated from source]
```

**Merge strategy:** preserve HUMAN-MAINTAINED sections verbatim; replace AUTO-GENERATED sections with
fresh data; merge frontmatter (add missing keys, refresh `last_updated`).
