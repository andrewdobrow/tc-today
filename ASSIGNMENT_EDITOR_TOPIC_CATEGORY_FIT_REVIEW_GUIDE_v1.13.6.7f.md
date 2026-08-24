# Assignment Editor Topic Category-Fit Review Guide — v1.13.6.7f

## Purpose
Give Sonnet 5 real assignment-editor veto authority on topic pages without building another brittle deterministic exclusion taxonomy into the prompt.

## Expected topic-page behavior
For Local Government, Crime & Safety, Business & Development, Sports, Things To Do, and Florida, the editor must first produce one category-fit decision for every source. Only `fits_category:true` sources may be assigned to hero/cards.

The prompt should contain the generic instructions that the editor must independently judge whether each source belongs in the section and must not assume upstream routing is correct. It should not contain a weather-specific Crime & Safety exclusion rule.

## Expected county-page behavior
Martin County, St. Lucie County, and Indian River County do not receive the additional topic-fit schema. Their assignment-editor job remains geographic/editorial ranking. A weather story can therefore be valid on a county page when it is genuinely about that county.

## Production verification
On the next manual assignment-editor shadow run:
1. Open `data/assignment-editor-shadow-report.json` before judging model behavior.
2. For any topic category, inspect `assignment_diagnostics.category_fit_decisions`.
3. Verify `category_fit_complete` is true.
4. Verify rejected source indexes never appear in `selected_source_indexes`.
5. In Crime & Safety specifically, confirm obvious non-crime candidates are rejected by the editor if upstream routing still admits them.
6. County pages should show `category_fit_required: false`.

## Important non-goal
This increment does not fix the separate final live hero-reconciliation corruption observed in the Aug. 24 St. Lucie comparison. Keep that defect on the bug list as a separate isolated increment.
