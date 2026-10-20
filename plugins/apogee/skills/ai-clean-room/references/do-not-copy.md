# What Is Protected, What Is Not, and How to Handle Each Element

For deciding about a specific element of the reference product. Not legal advice; where the note
says "lawyer", a short consultation is the intended action.

## Regimes in one table

| Element of the reference | Regime | Default handling |
|--------------------------|--------|------------------|
| Functionality, features, workflows, methods of operation, algorithms as such | Not copyright-protected (US §102(b); EU 2009/24/EC art. 1(2); SAS v. WPL C-406/10; RU Civil Code 1259(5)) | Reproduce freely from public docs and observation |
| Source and object code, scripts, resources inside the bundle | Copyright | Never accessed, never extracted. Observation only |
| Help texts, UI strings, tooltips, release notes, marketing copy | Copyright | Write your own. The spec records information content, not wording |
| Icons, images, sounds, fonts, mascots | Copyright; sometimes font licenses | Own assets. Do not trace or recolor the reference's |
| Layout, colors, overall look | US trade dress and design patents; EU/UK registered and unregistered designs; RU industrial design | Own design from your own design system or platform guidelines. Screenshots never reach implementation |
| Product name, feature names that function as marks, logo | Trademark | Own name; own feature names. Descriptive reference only ("compatible with X servers"), no logos, no suggestion of affiliation; wording confirmed by a lawyer if used publicly |
| Public protocols and formats (SFTP, FTP, S3, WebDAV, SSH config) | Public standards | Implement from the standards' documents, cite them in the spec |
| Proprietary formats (sync files, bookmark exports, droplet-like bundles) | Format structure is unprotected as such; embedded content may be protected; EU sui generis database right for datasets | Reproduce only the structure needed for import/export compatibility, learned from using the product and its public docs; no embedded data copied |
| Keyboard shortcuts, menu structure | Mostly methods of operation (Lotus v. Borland, US 1st Cir.); distinctive schemes may be contested | Follow platform conventions; do not mirror a distinctive scheme item by item |
| Patented techniques | Patents; clean room is no defense | If a feature looks unusual or the vendor is known for patents, ask a lawyer for a quick freedom-to-operate look before release |

## Observation methods

Allowed by default: using the product as a normal licensed user; reading its public documentation,
blog posts, support articles; looking at files the product writes for the user and traffic it
sends over public protocols; comparing with public standards.

Not used in this skill's scope: decompiling, disassembling, extracting strings or resources from
the bundle, circumventing license checks or protections, scraping the vendor's service against its
terms. If one of these ever seems necessary, that is the safety line in SKILL.md: stop and ask a
lawyer. The EU (Directive 2009/24/EC art. 6), the US (DMCA §1201(f)) and Russia (Civil Code art.
1280) each allow narrow decompilation for interoperability under conditions, but using those
exceptions is a different process with its own evidence requirements.

## Reference terms kept for compatibility

Sometimes a term from the reference must appear for users to find a feature or for files to
interoperate (a file extension, a field name in an exported format, a protocol option). Record
each such term in the spec with the reason. Keep them out of the product name, package names and
marketing. If a term is also the vendor's mark, use it only descriptively and get the wording
confirmed.

## License and terms of the reference

Read the license/ToS once at the start and keep a dated copy in the research directory. Watch
for: bans on reverse engineering (observation of behavior is not reverse engineering of code, but
a lawyer should confirm if the clause is broad), limits on automated use, non-compete style
clauses in SaaS terms. In the EU and UK, observing, studying and testing a lawfully used program
cannot be contractually excluded (Directive 2009/24/EC art. 5(3) and 8; CDPA s.50BA); in the US
contractual bans are generally enforceable (Bowers v. Baystate), so a broad clause there is worth a
lawyer's reading.
