# Release Check (black-box edition)

Run before the first public release and before releases that add user-facing features or change
branding. Answer each item with where the evidence is.

## Name and marks
- [ ] Product name cleared: trademark search in target markets (USPTO, EUIPO, UKIPO, Rospatent,
      WIPO Global Brand Database), domain and store listing available.
- [ ] No reference marks or vendor-specific feature names in UI text, identifiers, package names,
      file names, URLs, store listing or marketing.
- [ ] Any descriptive reference to the vendor or its product is factual, uses no logos, carries a
      "not affiliated" note, and its wording was confirmed.

## Texts and assets
- [ ] All UI strings, help, onboarding and release notes written by the team; no reference
      wording.
- [ ] Icons, images, sounds, fonts are the team's own or licensed; provenance recorded.
- [ ] Design derived from the product's own design system or platform guidelines; no reference
      screenshots in design or implementation tasks.

## Code and data
- [ ] No reference code, extracted resources or embedded datasets anywhere in the repository
      (spot check: identifiers, magic constants, comments mentioning the reference).
- [ ] Interoperable formats implemented from public standards or from documented structure only;
      sample files are team-created.
- [ ] Dependency license scan done; licenses compatible with the product's license; attribution
      notices included.

## Research hygiene
- [ ] Research directory is git-ignored and not shipped; no screenshots in the repository history.
- [ ] Scope note exists with the reference version, its license/ToS snapshot, and the statement
      that no reference code was in reach.

## Legal touchpoints
- [ ] Short lawyer check on: name clearance, descriptive references, any unusual feature that
      might be patented, any broad anti-reverse-engineering clause in the reference's terms.

Signed: <name>   Date: <YYYY-MM-DD>
