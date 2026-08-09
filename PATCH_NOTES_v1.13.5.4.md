# Treasure Coast Today v1.13.5.4 — Stale-Source Guard + Membership Conversion Cliffhanger

This is a cumulative replacement for the previously supplied v1.13.5.3 overlay. If v1.13.5.3 has not been applied, apply only this package on top of the current v1.13.5.2 repository state.

## Editorial integrity carried forward from v1.13.5.3

- New normal-news permalinks have a hard 48-hour source-age ceiling.
- Thin categories use archive recovery instead of publishing stale material merely to fill a section.
- Publisher-page contamination is bounded before identity decisions.
- Final-copy duplicate identity is independently derived and does not re-import poisoned source identity.
- Strong same-site delayed-reprint proof covers the Stuart Costco electrical-fire/reopening failure class.
- Pathological multi-incident catch-all registry records are automatically quarantined by structural rules.

## Membership conversion changes

### Character-bounded article cliffhanger

- Replaces the old paragraph-based preview with a character-bounded preview.
- A normal article exposes roughly 52% of paragraph one, never more than 300 characters.
- Paragraph two and all later paragraphs are member-only.
- The rest of paragraph one is also member-only and is never present in public HTML.
- The preview ends on a word boundary rather than cutting a word in half.

### Strong visible fade

- The final portion of the exposed teaser text visibly fades toward transparency.
- A larger vertical fade overlaps the bottom of the teaser before the coral paywall.
- This creates an intentional visual continuation cue without leaking protected text into source HTML.

### Seamless member unlock

- The protected payload carries the hidden continuation of paragraph one separately.
- On entitlement, the browser recombines the public prefix and protected continuation into a normal full first paragraph before displaying the rest of the article.

### Footer subscription ask

When membership is enabled, the footer now carries a distinct coral membership CTA:

- `Support local journalism`
- `Unlimited articles. No ads. Help fund independent Treasure Coast reporting.`
- `Subscribe`
- `$4.99/mo · $49/yr`

Dark launch retains the existing `Connect with TCT` footer treatment.

### Morning Brief remains explicitly free

Every inline Morning Brief module now visibly says:

- `Free newsletter`
- `Subscribe to the Morning Brief for free`

This deliberately distinguishes the free email product from the paid article membership.

## Additional correction

The footer generator is now truly launch-aware rather than carrying a literal unevaluated membership expression in its HTML template.

## Validation performed

- Generator runtime hotfix preflight: no changes required.
- Python compile checks passed for the modified generator and membership paywall helper in the available runtime.
- Focused stale-source, registry-containment, membership, launch and conversion tests: 65 passed.
- Membership-specific conversion suite: 31 passed.
- Package validation: 35 modules / 119 public exports passed.
- A representative 274-character lead exposed 138 characters and protected the remainder of paragraph one plus every later paragraph.

The complete GitHub **Test Editorial Engine** workflow remains the release gate before production.
