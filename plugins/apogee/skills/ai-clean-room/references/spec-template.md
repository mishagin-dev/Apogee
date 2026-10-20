# Specification Template (black-box edition)

The spec is the bridge between research and implementation. It is written in the team's own words,
describes behavior rather than the reference's look or wording, and is the only research-derived
document implementers read.

```markdown
# <Component or feature name, own term>

Version: <N>   Date: <YYYY-MM-DD>
Sources: public docs <links>, observed behavior in reference version <N>, standards <RFC/ISO>
Provenance note: no reference code, resources or texts were used; screenshots consulted during
research are not attached.

## 1. Purpose and scope
What the feature does for the user; what is in and out of scope for this version.

## 2. Terminology
| Term (own) | Meaning | Kept reference term for compatibility? (reason) |
|------------|---------|--------------------------------------------------|

## 3. Behavior
Given / When / Then rows, one observable behavior each.
| ID | Given | When | Then | Source |
|----|-------|------|------|--------|
| FR-001 | | | | |

## 4. Edge cases and errors
| ID | Condition | Expected behavior | Information the user must get (not wording) |
|----|-----------|-------------------|----------------------------------------------|

## 5. Formats and protocols
For anything that must interoperate: structure (grammar/schema/layout), which parts are required
for compatibility, which are free choices; reference to the public standard where one exists.
Sample files are team-created.

## 6. UI (functional only)
What information and controls each surface exposes and what they do. No layout, colors, icons,
spacing or animation; those come from the product's own design decisions.

## 7. Non-functional
Performance targets, platforms, security constraints (what is never logged or stored), accessibility.

## 8. Deliberate differences from the reference
Behaviors intentionally not reproduced or improved, with the reason.

## 9. Open questions
| ID | Question | Status |
|----|----------|--------|
```

Guidance:
- Prefer tables and grammars to prose.
- If a sentence starts with "the reference does it by ...", delete it: that is either unknowable
  (closed source) or irrelevant.
- Where behavior was inferred from experiments rather than documented, say so; those are the
  places where the product may legitimately differ.
