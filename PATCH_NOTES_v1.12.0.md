# Treasure Coast Today v1.12.0

## Authoritative Story Publication Ledger

This release changes persistent story identity from advisory metadata into a hard
publication constraint.

### Core invariant

A proven story, incident or exact source identity may own only one live TCT
permalink. A rewritten headline can no longer create a second article URL.

### Publication decision order

Every generated non-custom article is resolved before slug creation through:

1. Structured incident identity
2. Persistent editorial story ID
3. Exact normalized source-article URL
4. Existing custom-event authority
5. Weather-event identity
6. A conservative high-confidence same-event comparison when upstream story IDs fragmented

When any identity already owns a canonical publication, the writer must either
skip unchanged coverage or update that canonical page in place. The new-slug branch
performs a second ledger lookup immediately before writing. A high-confidence
same-event fallback also blocks parallel URLs when separate source URLs were given
fragmented registry IDs.

### Contextual updates

Registry-routed updates are now marked as update copy even when the source headline
does not use the word “update.” The first paragraph must explain the underlying
story and the new development. A contextless replacement is held and the existing
canonical page is preserved.

Automatic separate-link “major updates” are deliberately disabled in this release.
Until a later contract can require an explicit milestone, parent publication ID and
contextual lead, every automated development remains on the established canonical
URL. This prevents a wording change from being promoted into a supposed major update.

### Historical repair

The release reconciles duplicate archive records by connected identity evidence,
merges category memberships, repairs false headline/slug quarantines, removes
redirect sources from live surfaces and creates permanent redirects.

### Incident identity expansion

The structured identity layer now covers:

- Named-person death, mourning, memorial and cause-of-death coverage
- Large local animal-hoarding cases
- Named public-infrastructure assets experiencing the same operational condition

The Glades Cut Off Road “not operational” and “not working” traffic-light headlines
therefore share one deterministic identity. Crashes on the same road do not.

### Production reports

- `data/canonical-publication-ledger.json`
- `data/global-incident-identity-contract.json`
- `data/live-category-canonical-contract.json`
- `data/final-canonical-surface-contract.json`

### Emergency regressions

The release permanently covers the Geoffrey Lang article cluster and both Glades
Cut Off Road traffic-light URLs, alongside the previously established Ware, Big
Taste, infant-death and Martin County Fire Rescue cases.
