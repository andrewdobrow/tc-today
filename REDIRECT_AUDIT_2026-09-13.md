# Historical Redirect Audit — v1.13.9.20

## Scope

- Baseline audited: v1.13.9.19 repository state, **220** cumulative permanent redirects.
- The audit first flagged redirects whose source and target had incompatible subject/event evidence, then checked historical repository snapshots, archive/source lineage, and surviving canonical records.
- **29 redirects were confirmed erroneous.** Sixteen had sacrificed independent article permalinks and are removed/restored as standalone articles. Thirteen were genuine duplicate aliases pointed at the wrong story and are retargeted to the verified canonical.
- **2 suspicious-looking redirects were reviewed and intentionally retained** because historical evidence supports the source and target as the same event/story.
- Corrected manifest contains **204** permanent redirects. The net decrease is 16 because the 13 repaired aliases remain valid 301s.
- Ronald Corbin was the incident that triggered this audit; its bad redirect had already been removed/restored in v1.13.9.19 and remains protected in v1.13.9.20.

## REMOVE / RESTORE — confirmed independent stories

| Source permalink | Wrong target in .19 baseline | .20 action |
|---|---|---|
| `2026-06-29-palm-city-man-dies-after-suv-collides-with-semi-truck-on-floridas-turnpike-in-ma` | `2026-06-11-wrongful-death-lawsuit-filed-in-st-lucie-county-after-fatal-turnpike-crash-kille` | Remove 301; restore substantive standalone article |
| `2026-08-06-firefighters-battle-blaze-at-st-lucie-county-home-on-melaleuca-boulevard` | `2026-08-06-us-1-closed-in-both-directions-near-tiffany-avenue-in-port-st-lucie-after-crash` | Remove 301; restore substantive standalone article |
| `2026-08-06-flood-advisory-issued-for-western-martin-county-through-730-pm-thursday` | `2026-08-06-us-1-closed-in-both-directions-near-tiffany-avenue-in-port-st-lucie-after-crash` | Remove 301; restore substantive standalone article |
| `2026-08-06-us-1-closed-in-both-directions-near-tiffany-avenue-in-port-st-lucie-after-crash` | `2026-06-27-port-st-lucie-man-arrested-after-holding-teens-at-gunpoint-during-orbeez-prank` | Remove 301; restore substantive standalone article |
| `2026-08-09-2-year-old-horse-reported-stolen-from-pasture-in-port-st-lucie` | `2026-08-08-port-st-lucie-police-investigate-death-of-77-year-old-man-found-in-pond-near-his` | Remove 301; restore substantive standalone article |
| `2026-08-10-centennial-high-school-student-hit-by-car-at-port-st-lucie-intersection` | `2026-07-31-woman-86-dies-in-port-st-lucie-crash-after-failing-to-yield-at-intersection` | Remove 301; restore substantive standalone article |
| `2026-08-18-left-lane-of-i-95-southbound-blocked-near-stuart-due-to-roadway-debris` | `2026-07-31-woman-86-dies-in-port-st-lucie-crash-after-failing-to-yield-at-intersection` | Remove 301; restore substantive standalone article |
| `2026-08-21-donalds-pledges-20-insurance-cut-backs-data-centers-as-florida-governors-race-pi` | `2026-08-12-martin-county-reviews-first-development-proposal-under-new-state-agricultural-en` | Remove 301; restore substantive standalone article |
| `2026-08-21-sheriff-eric-flowers-credits-flock-license-plate-readers-in-vero-beach-murder-in` | `2026-07-31-woman-86-dies-in-port-st-lucie-crash-after-failing-to-yield-at-intersection` | Remove 301; restore substantive standalone article |
| `2026-08-24-fort-pierce-man-dies-after-bb-gun-shooting-suspect-charged-with-manslaughter` | `2026-08-06-12-year-old-describes-hit-and-run-that-injured-sister-in-fort-pierce` | Remove 301; restore substantive standalone article |
| `2026-08-24-funnel-cloud-spotted-over-port-st-lucie-neighborhood-during-tornado-warning-sund` | `2026-07-31-woman-86-dies-in-port-st-lucie-crash-after-failing-to-yield-at-intersection` | Remove 301; restore substantive standalone article |
| `2026-08-24-st-lucie-county-sheriffs-office-seeks-help-finding-fort-pierce-woman-missing-sin` | `2026-06-27-port-st-lucie-man-arrested-after-holding-teens-at-gunpoint-during-orbeez-prank` | Remove 301; restore substantive standalone article |
| `2026-08-27-corgi-found-three-streets-away-after-port-st-lucie-tornado` | `2026-06-27-port-st-lucie-man-arrested-after-holding-teens-at-gunpoint-during-orbeez-prank` | Remove 301; restore substantive standalone article |
| `2026-08-27-port-st-lucie-police-dispel-active-shooter-rumor-after-swat-operation-on-southea` | `2026-07-29-man-crashes-suv-into-port-st-lucie-liquor-store-charged-with-dui` | Remove 301; restore substantive standalone article |
| `2026-08-28-three-st-lucie-county-men-arrested-on-drug-charges-after-search-at-convenience-s` | `2026-08-25-ronald-corbin-martin-county-high-school-choral-teacher-for-34-years-dies` | Remove 301; restore substantive standalone article |
| `2026-09-01-port-st-lucie-police-search-for-missing-38-year-old-man-last-seen-monday-morning` | `2026-08-24-st-lucie-county-sheriffs-office-seeks-help-finding-fort-pierce-woman-missing-sin` | Remove 301; restore substantive standalone article |

## RETARGET — duplicate alias, wrong destination

| Alias permalink | Wrong target in .19 baseline | Verified .20 target |
|---|---|---|
| `2026-08-09-2-year-old-stallion-stolen-from-pasture-in-port-st-lucie` | `2026-08-08-port-st-lucie-police-investigate-death-of-77-year-old-man-found-in-pond-near-his` | `2026-08-09-2-year-old-horse-reported-stolen-from-pasture-in-port-st-lucie` |
| `2026-08-09-american-paint-horse-stolen-from-pasture-in-port-st-lucie-sheriffs-office-seeks` | `2026-08-08-port-st-lucie-police-investigate-death-of-77-year-old-man-found-in-pond-near-his` | `2026-08-09-2-year-old-horse-reported-stolen-from-pasture-in-port-st-lucie` |
| `2026-08-09-american-paint-horse-stolen-from-port-st-lucie-pasture-sheriffs-office-seeks-pub` | `2026-08-08-port-st-lucie-police-investigate-death-of-77-year-old-man-found-in-pond-near-his` | `2026-08-09-2-year-old-horse-reported-stolen-from-pasture-in-port-st-lucie` |
| `2026-08-09-horse-reported-stolen-from-pasture-on-williams-road-in-port-st-lucie` | `2026-08-08-port-st-lucie-police-investigate-death-of-77-year-old-man-found-in-pond-near-his` | `2026-08-09-2-year-old-horse-reported-stolen-from-pasture-in-port-st-lucie` |
| `2026-08-09-horse-reported-stolen-from-port-st-lucie-pasture-sheriff-seeks-public-help` | `2026-08-08-port-st-lucie-police-investigate-death-of-77-year-old-man-found-in-pond-near-his` | `2026-08-09-2-year-old-horse-reported-stolen-from-pasture-in-port-st-lucie` |
| `2026-08-09-st-lucie-county-sheriffs-office-searches-for-stolen-american-paint-horse-from-wi` | `2026-08-08-port-st-lucie-police-investigate-death-of-77-year-old-man-found-in-pond-near-his` | `2026-08-09-2-year-old-horse-reported-stolen-from-pasture-in-port-st-lucie` |
| `2026-08-09-st-lucie-county-sheriffs-office-seeks-help-finding-horse-stolen-from-port-st-luc` | `2026-08-08-port-st-lucie-police-investigate-death-of-77-year-old-man-found-in-pond-near-his` | `2026-08-09-2-year-old-horse-reported-stolen-from-pasture-in-port-st-lucie` |
| `2026-08-10-centennial-high-school-student-hit-by-car-while-crossing-crosstown-parkway-in-po` | `2026-07-31-woman-86-dies-in-port-st-lucie-crash-after-failing-to-yield-at-intersection` | `2026-08-10-centennial-high-school-student-hit-by-car-at-port-st-lucie-intersection` |
| `2026-08-27-corgi-found-three-streets-away-after-ef0-tornado-in-port-st-lucie` | `2026-06-27-port-st-lucie-man-arrested-after-holding-teens-at-gunpoint-during-orbeez-prank` | `2026-08-27-corgi-found-three-streets-away-after-port-st-lucie-tornado` |
| `2026-08-28-corgi-found-three-streets-away-after-ef0-tornado-in-port-st-lucie` | `2026-06-27-port-st-lucie-man-arrested-after-holding-teens-at-gunpoint-during-orbeez-prank` | `2026-08-27-corgi-found-three-streets-away-after-port-st-lucie-tornado` |
| `2026-08-28-corgi-reunited-with-owner-after-ef0-tornado-in-port-st-lucie` | `2026-06-27-port-st-lucie-man-arrested-after-holding-teens-at-gunpoint-during-orbeez-prank` | `2026-08-27-corgi-found-three-streets-away-after-port-st-lucie-tornado` |
| `2026-09-02-port-st-lucie-police-pause-flock-camera-use-after-state-revokes-permits-on-state` | `2026-07-29-man-crashes-suv-into-port-st-lucie-liquor-store-charged-with-dui` | `2026-09-01-st-lucie-county-sheriff-restricts-license-plate-reader-use-to-forcible-felonies` |
| `2026-09-03-fort-pierce-police-arrest-16-year-old-suspect-within-24-hours-in-armed-robbery-c` | `2026-09-02-indian-river-county-sheriffs-office-assists-fellsmere-police-in-search-for-mache` | `2026-09-05-fort-pierce-police-arrest-16-year-old-within-24-hours-in-armed-robbery-involving` |

## KEEP — suspicious but historically verified

| Source permalink | Retained target | Reason |
|---|---|---|
| `2026-08-09-st-lucie-county-sheriffs-office-warns-against-using-social-media-to-report-crime` | `2026-08-08-port-st-lucie-man-arrested-after-video-shows-him-kicking-small-dog` | Historical source/article review shows this was another URL for the same Port St. Lucie dog-abuse arrest coverage; its existing canonical target is retained. |
| `2026-09-01-body-found-in-martin-county-mangroves-believed-to-be-missing-port-st-lucie-man` | `2026-08-29-martin-county-sheriffs-office-searches-for-missing-oklahoma-visitor-last-seen-at-chastain-beach` | Historical/current source review identifies the body as missing visitor Michael Anthony Debevec, so this is a material update to the existing Debevec canonical and the redirect is retained. |

## Prevention added in .20

- A shared persistent story ID is not sufficient authority for destructive permalink consolidation.
- A structured incident anchor is not sufficient authority for destructive permalink consolidation.
- Historical canonical-ledger, known-event, structured-incident, and unified-incident consolidation paths now re-prove the **actual source→target pair** before writing a permanent redirect.
- The 16 recovered standalone permalinks are explicit fail-closed regression anchors. A future current-run attempt to redirect any of them stops the production run before `_redirects` is written.
- The 13 repaired aliases are target-locked. A future attempt to point one at a different story stops the production run.
- The cumulative redirect manifest is repaired during final enforcement, so stale historical redirects cannot silently reappear merely because they were written in an older run.

## Conservative boundary

This audit does **not** claim that every remaining historical redirect is independently re-proven from scratch. The remaining redirects showed no cross-story mismatch requiring correction under this audit and are preserved to avoid damaging legitimate SEO migrations. The new runtime pairwise-authority gates apply to future destructive consolidation.
