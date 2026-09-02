# TCT v1.13.7.1j — Material-update headline progression + stale-canonical repair

## Production symptom

After v1.13.7.1i, the Debevec material-update transaction finally reached the existing Aug. 29 canonical and refreshed article content, but the public display headline remained the original search-era headline:

> Martin County Sheriff's Office searches for missing Oklahoma visitor last seen at Chastain Beach

That is not an acceptable material update. A body-recovery development can be present in the article body while remaining effectively invisible to readers if the H1/title still describes only the original search.

## What this release changes

### 1. Headline progression is now part of semantic material-update validation

`tct_engine/semantic_material_update.py` moves the composer contract to version 1.1.

A validated material-update composition must now:

- change the visible headline from the pre-update canonical headline; and
- surface at least one token from the semantic gate's recorded novel facts (falling back to the incoming update headline only when the gate supplied no usable novelty tokens).

The permalink remains immutable. This check governs the visible headline only.

If the article body/lead passes all existing composition contracts and the only failure is headline progression, the composer gets one explicit correction attempt. A second failure remains fail-closed.

### 2. Current-run publication invariant now checks the committed headline

The no-silent-loss invariant introduced in v1.13.7.1h previously proved that a selected material update reached the canonical transaction. It did not prove that readers could see the changed story state in the headline.

The invariant now records the pre-update canonical headline and selected generated headlines. A current-run semantic update is considered committed only when the semantic publication report contains the target canonical **and** the committed `updated_headline` differs from the old canonical headline.

A stale committed title now raises:

`MATERIAL UPDATE HEADLINE INVARIANT FAILED`

instead of allowing a green production run.

### 3. Repair for already-committed stale semantic-update headlines

The Debevec source was already absorbed by v1.13.7.1i, so simply strengthening future composition would not reliably replay that same source on the next run.

`write_archives()` therefore contains a conservative repair for previously committed semantic material updates whose body changed while the headline did not.

The repair runs only when the canonical archive row has all of the following persisted authority:

- `meaningful_update_validated = true`
- `meaningful_update_basis = semantic_material_update_gate`
- the immutable `permalink_origin_headline`
- recorded semantic `novel_facts`
- a persisted `latest_source_headline`

The current headline must fail material-update headline progression, while the persisted latest-source headline must pass it. The source headline must also be between 5 words and 180 characters. Known publisher attribution suffixes are removed.

When those conditions hold, TCT updates the existing article's display headline in place across:

- archive metadata
- `<title>`
- Open Graph title
- Twitter title when present
- article H1
- article image alt text
- JSON-LD `NewsArticle.headline`
- share-text headline

It does **not** change the canonical slug, `permalink_origin_headline`, or `custom_headline_key`, and it does not rewrite the article body.

The repair is reported in:

`data/material-update-headline-repair.json`

and logs:

`Material-update headline repair refreshed N stale canonical headline(s) without changing permalinks`

## Regression coverage

Added coverage for the exact production failure class:

- a valid material-update body with the old canonical headline is rejected;
- a headline-only composer miss gets one correction attempt;
- retroactive material updates must evolve the canonical headline while retaining the canonical URL;
- the terminal publication invariant fails when a selected material update commits with the old headline;
- an already-committed Debevec-style body update repairs the stale H1/title from persisted source authority without changing the Aug. 29 slug or custom identity key;
- a canonical whose material-update headline already advances the story is left untouched.

The stale-headline replay was also exercised against the actual retained TCT Aug. 29 Debevec article shell: all six stored occurrences of the old display headline were removed from the copied page, the replacement headline was applied, the permalink stayed unchanged, and article content remained intact.

## Validation

Focused material-update/custom-authority suite:

- 56 passed
- 0 failed

Exact Test Editorial Engine pytest target:

- 1,087 passed
- 0 failed
- 44 existing `datetime.utcnow()` deprecation warnings

Package validation:

- passed
- 38 modules imported
- 122 public exports verified

## Production acceptance

This release is not considered production-proven until a real Generate News run leaves the Aug. 29 Debevec canonical with a body-recovery headline on the public article while retaining the existing permalink.
