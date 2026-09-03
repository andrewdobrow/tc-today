# v1.13.7.1t — St. Lucie ALPR Custom Authority + Missing-Person Identity Integrity

Apply this overlay directly over **v1.13.7.1s**.

## Production regression

Two TCT permalinks were allowed to represent the same short-lived St. Lucie automated-license-plate-reader policy episode:

- canonical authoritative custom article:
  `2026-09-01-st-lucie-county-sheriff-restricts-license-plate-reader-use-to-forcible-felonies`
- escaped generated URL:
  `2026-09-02-port-st-lucie-police-pause-license-plate-readers-limit-use-to-life-threatening-s`

A previously escaped generated PSLPD ALPR URL was also already present in canonical redirect history and was incorrectly pointed at an unrelated DUI article:

- `2026-09-01-port-st-lucie-police-pause-flock-camera-use-after-state-revokes-permits`

## Root causes repaired

### 1. Literal `missing` text could poison event identity

`extract_article_facts()` previously classified any article containing the word `missing` as a missing-person event. The WPBF ALPR policy source contains examples such as a "missing or endangered child" and describes the technology as useful for locating missing people. Those are policy/use-case references, not the event being reported.

The extractor now requires active missing-person incident evidence: search/seek language governing a missing subject, direct missing-subject phrasing, reported/remains missing, last-seen/whereabouts evidence, Amber/Silver alerts, or found/located-safe resolution language. Policy buckets such as `missing-person cases` no longer create a missing-person event.

### 2. City-level missing-person keys could merge unrelated incidents

`missing-person-port-st-lucie` was previously allowed to own a persistent story mapping. That is a class of incidents, not one incident. Current event-key generation now appends the same stable article/source suffix used for crash and fire classes.

`registry_repair.REPAIR_VERSION` is bumped from 15 to **16** and unsuffixed `missing-person-*` keys are now broad/unsafe. This makes existing contaminated mappings repairable instead of permanently authoritative.

A dry-run of repair v16 against the exact repository state used for this patch quarantined the contaminated `story_002646` and removed the `missing-person-port-st-lucie` event mapping.

### 3. Authoritative custom coverage had no durable contract for this ALPR policy episode

A narrow custom-authority identity contract now binds same-window St. Lucie ALPR/Flock **policy restriction/removal** coverage to the authoritative custom article when both sides independently contain:

- ALPR/license-plate-reader/Flock-camera topic language in headline/source-headline;
- pause/limit/restrict/suspend/remove/revoke/directive policy-action language;
- St. Lucie or Port St. Lucie locality; and
- publication dates within four days.

The contract is intentionally headline/source-headline scoped so an ordinary homicide, arrest, or other incident story that merely mentions Flock evidence in its body does **not** collapse into the policy article.

### 4. Both escaped public URLs are permanently repaired

Canonical cleanup now forces both known generated ALPR policy slugs to the Sept. 1 authoritative custom permalink. This also overwrites the stale Sept. 1 redirect-to-DUI record. The known false `missing-person` event family is removed from the custom canonical's persisted display-copy identity.

The Story Regression production gate now requires:

- the custom ALPR canonical to remain in archive;
- both escaped generated slugs to have redirect records;
- both redirects to target the exact custom canonical and remain marked custom-authoritative;
- both source slugs to be absent from archive; and
- both final redirect HTML pages to verify.

## Regression coverage

New/updated tests cover:

- ALPR policy/use-case wording not becoming a missing-person incident;
- real missing-person search wording still extracting correctly;
- two different same-city missing-person articles receiving different event keys;
- unsuffixed missing-person keys never owning a StoryRegistry mapping;
- representative `story_002646` contamination being quarantined;
- exact PSLPD/custom ALPR durable identity;
- unrelated Flock-assisted incident coverage staying separate;
- generated ALPR copy collapsing into custom authority;
- stale redirect-to-DUI being overwritten by the custom canonical;
- both known redirect pages being created and verified; and
- the Story Regression gate failing closed around this production case.

## Validation on the exact v1.13.7.1s repository snapshot

- Test Editorial Engine equivalent:
  `python -m pytest tests -q --ignore=tests/test_canonical_identity.py --ignore=tests/test_matcher_contract.py`
  - **1114 passed, 0 failed, 48 warnings**
- Focused identity/custom/redirect suite: **76 passed, 0 failed** before the final additional contamination regression was added; final complete suite is authoritative.
- `python scripts/validate_package.py`:
  - **38 modules imported / 122 public exports verified**
- `py_compile` passed for all changed production Python modules.
- repository 90 MiB guard: **clean**
- exact WPBF ALPR policy-text probe after the fix:
  - `event_types = ()`
  - no `missing person` fact
  - event key no longer uses `missing-person-port-st-lucie`
- repair-v16 dry-run on the current registry:
  - `story_002646` moved out of active stories into quarantine
  - `missing-person-port-st-lucie` mapping removed

No editorial confidence threshold, materiality threshold, canonical cleanup confidence threshold, or model decision threshold was lowered.

## Production acceptance

1. Run **Test Editorial Engine** first. Do not run Generate News unless it is green.
2. If green, run exactly **one Generate News**.
3. Verify both generated ALPR URLs redirect to:
   `2026-09-01-st-lucie-county-sheriff-restricts-license-plate-reader-use-to-forcible-felonies`
4. Verify the Sept. 1 generated PSLPD URL no longer targets the unrelated DUI article.
5. Verify `archive.json`, RSS, sitemap, homepage/category surfaces contain only the authoritative custom canonical for this policy episode.
6. Verify `data/story-regression-report.json` passes all `st_lucie_alpr_*` checks.
7. Verify `data/canonical-redirects.json` contains both exact source slugs with the exact custom target.
8. Inspect editorial observability/audit to confirm current ALPR policy sources are not assigned a generic `missing-person-port-st-lucie` event identity or the contaminated `story_002646`.
