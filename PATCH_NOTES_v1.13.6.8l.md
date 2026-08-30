# Treasure Coast Today v1.13.6.8l
## Authoritative Custom Missing-Person Continuity

### Problem
A later publisher version of the Micheal/Michael Anthony Debevec II missing-person case was able to mint a second TCT permalink instead of resolving to the existing authoritative custom article.

The escaped duplicate was:

`2026-08-30-martin-county-sheriffs-office-searches-for-missing-oklahoma-man-last-seen-at-hut`

The authoritative custom canonical remains:

`2026-08-29-martin-county-sheriffs-office-searches-for-missing-oklahoma-visitor-last-seen-at-chastain-beach`

The failure had two layers:

1. The older custom-incident matcher saw the wording-drifted publisher version at only 77% fuzzy confidence, below its 95% suppression threshold, even though unified incident evidence identified the named missing-person case at 98% confidence.
2. A fragmented registry route could classify the later source as `new_story`, so it never reached normal material-update evaluation against the authoritative custom permalink.

### Fix
- Adds a narrow durable identity contract for authoritative custom missing-person coverage.
- Requires both sides to be missing-person incidents, an exact shared strong participant name, and unified incident confidence of at least 0.96.
- Expands missing-person family/concept recognition for publisher wording such as `searching for ... disappeared`, `disappearance`, and family-not-heard-from phrasing.
- Lets `_published_skip_canonical()` resolve a later publisher source to an authoritative custom canonical even when the registry assigned a fragmented/new story ID.
- Once resolved, the existing semantic material-update gate remains authoritative:
  - material new facts -> update the custom canonical in place;
  - no material advancement -> suppress as duplicate.
- Adds a permanent migration for the already-escaped Debevec duplicate URL. It is removed from the active archive and rendered as a noindex 301-style canonical redirect to the original custom permalink.

### Safety boundaries
This does not introduce generic same-city or same-topic missing-person merging. Durable matching requires a shared named participant plus conservative unified-incident evidence. Existing semantic materiality logic is not weakened or bypassed.

### Validation
- Exact production-data probe: later Debevec publisher wording resolves to the authoritative custom slug with basis `durable_custom_incident_identity:missing-person|michael-anthony-debevec`.
- Focused missing-person/custom-canonical regression group: 63 passed.
- Full CI-equivalent suite: 1,038 passed, 0 failed.
- Package validation: 38 modules imported, 122 public exports verified.

### Expected production behavior
On the next successful Generate News run:
- the known Aug. 30 duplicate permalink should redirect to the Aug. 29 authoritative custom permalink;
- the duplicate should disappear from active archive/homepage/category surfaces;
- if the richer publisher source is still eligible and materially advances the case, the normal semantic material-update path can refresh the original custom article rather than creating a new URL.
