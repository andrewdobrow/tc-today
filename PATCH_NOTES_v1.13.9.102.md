# TCT v1.13.9.102 — Packard custom-body fidelity hardening

- Fixes the production Packard failure where `validate_custom_body_fidelity()` reported `article body missing` even though the article body rendered.
- The fidelity validator now extracts `.article-body` directly instead of requiring a specific sponsorship/newsletter/share sibling sequence after the body.
- Supports additional classes on the article-body element.
- Does not change Packard copy, carousel, sponsorship disclosures, custom queue contents, deduplication, redirects, membership behavior, or publication ranking.
- Adds a regression proving Packard fidelity survives additional post-body modules and an augmented article-body class.
