---
name: ai-clean-room
description: >-
  Personal black-box clean-room skill: build an independent product that reproduces the
  functionality of a closed-source reference application using only its public documentation,
  observed behavior and screenshots, without copying its code, texts, icons, design or name.
  Manual invocation only (/ai-clean-room).
disable-model-invocation: true
---

# AI Clean Room (black-box edition)

Scope of this skill: the reference product is closed source, nobody on the project has its code,
and the research consists of public documentation, using the product, and screenshots. In that
situation functionality, ideas and methods of operation are not protected by copyright (US 17
U.S.C. §102(b); EU Directive 2009/24/EC art. 1(2); Russia, Civil Code art. 1259(5)), so there is
no code to avoid copying. What is protected is the reference's expression: texts, UI strings,
icons, graphics, layout and look, embedded data, documentation, and its name and marks. The whole
job of this skill is to keep those out of the product while the research stays useful as context.

Not legal advice. Trademarks, design rights and patents are separate regimes that clean room does
not address; a short check with a lawyer before release is still the right move.

**Safety line.** If at any point the reference's source code, decompiled output, leaked material,
or a person who worked on it enters the project, stop: that is a different regime (information
barrier, separate teams, evidence logs). Say so and consult a lawyer before continuing. Do not try
to improvise the heavy process from memory.

## 1. How research and implementation relate

- Research (feature inventories, documentation summaries, screenshots, notes) lives in a
  git-ignored directory of the project (for example `docs/apogee/business/` or `research/`). It
  is context for writing the spec and for product decisions. It is never committed.
- The spec and the decision records live in the project's normal docs and are the input for
  implementation. They describe behavior and decisions in the team's own words, with no quotes
  from the reference's help texts, no screenshots, and no reference names.
- Implementation prompts and tasks are written from the spec and decisions, not from the raw
  research. "Implement the queue behavior from spec §4" is right; "make it work like in the
  screenshot" is wrong, because the screenshot carries the reference's design.
- No separate workspaces, worktrees, roles or handoffs are needed. Everything happens inside the
  project directory the user named; do not create directories, worktrees or branches outside it.

## 2. What may be taken from the reference and what may not

| Take freely | Do not take |
|-------------|-------------|
| What the product does: features, workflows, behaviors, edge cases, error conditions | Its code, scripts, resources extracted from the bundle (icons, images, sounds, strings, plists) |
| Public protocols and formats it speaks (SFTP, S3, WebDAV, ...) via their public specs | Its proprietary file formats beyond what interoperability needs, and any embedded data sets |
| The information a message must convey | The wording of its messages, tooltips, help, release notes |
| The fact that a UI has two panes, a queue, a server list | Its layout, spacing, colors, icons, animations, typography, overall look |
| The fact that it supports a feature named X | The name X in your UI, identifiers, file names or marketing, if X is its own term or mark |
| Keyboard conventions that are platform or category standards | Distinctive shortcut schemes or command hierarchies that are its own |
| Observed behavior from using it as a normal user | Anything learned by decompiling, disassembling, or circumventing its protection |

Details and the reasoning per regime: `references/do-not-copy.md`. Load it when deciding about a
specific element (a name, an icon style, a format, a message) or when the user asks "is this ok".

## 3. Working with screenshots

Screenshots are fine in research for understanding what a feature does. Rules that keep them
harmless:
- They stay in the git-ignored research directory, never in the repository, docs that ship, or
  issue tracker attachments that become public.
- The spec describes what the screenshot shows functionally ("the transfer list shows name, size,
  progress and a cancel control per row"), not how it looks.
- UI implementation is briefed from the spec plus the product's own design decisions (platform
  guidelines, its own design system). Never paste a reference screenshot into a UI implementation
  prompt or ask an agent to match it.
- If a screenshot is needed to explain an edge case to an implementer, describe the behavior in
  words instead.

## 4. Minimal process

1. **Scope note** (once, in the project docs): reference product and version, what is being
   reproduced functionally, what is deliberately the product's own (name, design, texts), the
   reference's license/ToS read and respected, confirmation that no reference code is in reach.
2. **Research** into the git-ignored directory, with a line per source (public doc URL, "observed
   in version N", screenshot file).
3. **Spec** per `references/spec-template.md`: behavior, formats, protocols, edge cases, non-goals,
   deliberate differences. Own terminology; mark any reference term kept for interoperability.
4. **Implement** from the spec in the normal workflow (issue tracker, branches, reviews). Code,
   identifiers, strings and assets are the product's own.
5. **Before release** run `references/release-check.md`: name clearance, no reference marks in
   UI/identifiers/package names, own icons and texts, dependency licenses, a patent sanity check
   with a lawyer if the feature set is unusual.

Write the scope note before research starts; everything else is ordinary development.

## 5. Writing implementation prompts

- Reference the spec section; state constraints (language, architecture, conventions) as facts.
- Do not name the reference product, its company or its own feature names.
- Do not include quotes from its documentation, its message texts, or screenshots.
- For UI tasks, point at the product's own design tokens or platform guidelines, not at the
  reference.
- Ask the implementer to write its own identifiers and strings and to flag anything in the spec
  that is unclear instead of guessing from "how such apps usually work".

## 6. How to answer the user

- Say whether the request is inside this skill's scope (black-box, closed source, no code) or
  trips the safety line. Then give the action.
- When asked "can I copy X", answer per the table in §2 with the regime involved (copyright,
  trademark, design) and whether a lawyer should confirm. Never say "this is legal"; say "this is
  low risk because ..., confirm with a lawyer if ...".
- Keep the process at the size described in §4. If you find yourself proposing roles, handoff
  logs, declarations or a second workspace, you have left this skill's scope; check the safety
  line instead.
- Do not propose alternative architectures or heavier processes unless asked.

## 7. Self-check before replying

- Did the reply quote the reference's texts, name its own terms in product-facing places, or
  attach its screenshots to an implementation task?
- Did it propose creating anything outside the project directory or without asking?
- Did it keep the process to §4?
