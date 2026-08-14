# TCT v1.13.6.1 — Follow-up evidence precision

This Phase B increment improves the precision of follow-up detection evidence without changing live publication behavior.

## Why this increment

Production observability reported 9 retrospective follow-up transitions as activation-eligible. Manual review showed that 6 were the same publisher article URL evolving in place, not distinct follow-up publications. Another apparent death milestone was already present semantically in the prior headline (`suspected suicide`). The evidence was therefore not precise enough to activate safely.

## Changes

- Separates exact same-source-article evolution from distinct follow-up candidates.
- Adds `same_source_evolution_count`, milestone counts, and examples to retrospective observability.
- Makes retrospective `candidate_count` explicitly represent `distinct_article_transitions`.
- Recognizes `deadly`, `fatal`, `fatality/fatalities`, `suspected/apparent suicide`, and `died by suicide` as death evidence so death is not falsely treated as novel.
- Normalizes all `unknown-event-*` keys to the same unknown family for retrospective diagnostics.
- Treats a conflict between two *known* event families as an activation blocker while avoiding false conflicts when either side is unknown.
- Keeps all follow-up candidate behavior observe-only. No story grouping, canonical selection, ranking, or publication behavior is changed.

## Expected production effect

The follow-up report should contain fewer false activation candidates and clearly distinguish source-article evolution from genuinely separate follow-up reporting. This gives the next guarded activation increment a much cleaner evidence base.
