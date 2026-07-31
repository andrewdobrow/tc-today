# Treasure Coast Today Editorial Engine v1.12.0.7

## Event Identity Authority Boundary

This release fixes the architectural cause of the v1.12.0.6 cross-source identity failures. Fuzzy similarity may now retrieve a possible related story, but it cannot authorize mutation of an established permalink.

### Core changes

- Separates candidate retrieval from canonical publication authority.
- Introduces three explicit identity outcomes:
  - `same_event_verified`
  - `possible_relationship`
  - `new_story`
- Permits canonical writes only for deterministic identity or a hard composite of source-derived event facts.
- Requires a target-bound canonical write authorization immediately before an existing page can be changed.
- Treats legacy similarity scores as compatibility diagnostics rather than probabilities.
- Persists an immutable `event_identity` record when a story is first published. Generated TCT prose, background paragraphs, quotes and related incidents cannot later redefine that identity.
- Prevents untrusted or fragmented story IDs from becoming write authority merely because they exist.
- Keeps candidate-only relationships from changing the incoming route, story ID, story form or canonical slug.

### Authoritative identity paths

A write to an established canonical page may be authorized by:

- exact normalized source URL;
- registry-certified persistent story ID;
- exact structured incident key with independent corroboration;
- exact custom or weather event key;
- hard composite event proof such as the same incident participant and precise location, or the same governing body and specific policy subject with multiple distinctive facts.

County, agency, event category, headline similarity and broad body-word overlap remain useful for candidate retrieval only.

### Final write gate

Before any existing permalink is mutated, the writer independently verifies a target-bound authorization token or an explicit deterministic identity path. Missing authority fails closed: the existing page is preserved and the incoming item cannot overwrite it.

### Observability

- Adds `data/event-identity-authority.json`.
- Updates `data/cross-source-update-identity.json` to schema version 2.
- Reports verified identities, candidate-only relationships and unauthorized destructive actions separately.
- The report fails when a candidate-only relationship reaches a destructive publication action.

### Release metadata

- Engine version: `1.12.0.7`
- Release: `event-identity-authority-boundary`
- Observability schema: `21`
- Canonical publication ledger: `1.1`
