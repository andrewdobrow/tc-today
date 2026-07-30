# Treasure Coast Today v1.12.0.1

## Final category identity scope hotfix

The first v1.12.0 production run completed archive reconciliation and permalink
binding, then stopped before final category canonicalization because `main()` passed
an undefined `_publication_identity` variable. That variable was local to
`write_archives()` and was never valid in `main()`.

This hotfix removes the invalid cross-function reference. The final category
canonicalization and validation functions now use their existing self-loading
interface, which reads the persisted editorial story registry from the output root.

No deduplication policy, canonical-selection rule, incident matcher, update-context
rule, or publication-ledger behavior was weakened or bypassed.

## Regression coverage

A permanent AST-level regression verifies that:

- `main()` never loads `_publication_identity`.
- Both final category contracts are invoked.
- Neither call depends on a local `identity_index` keyword.

The release remains `authoritative-story-publication-ledger`; only the patch version
advances to `1.12.0.1`.
