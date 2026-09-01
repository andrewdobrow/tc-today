# v1.13.7.1c production review

After applying over v1.13.7.1b and running Generate News:

1. Clear `tct_monthly_free_article_v1` from site local storage (or use a fresh browser profile) so the test article is granted as the monthly free article.
2. Open a long protected article.
3. Confirm every story paragraph/section is readable continuously before the membership card.
4. Confirm the post-read card begins with `You've read your free article this month.` and appears immediately before the article newsletter/share area.
5. Open a different protected article and confirm the normal `Continue reading Treasure Coast Today for just $1.` wall still appears after the teaser.
6. Re-open the original free article and confirm it remains fully readable with the card only after the final story content.

The key DOM invariant after the first free unlock is: no unlocked `#tct-protected-content` may remain inside `.tct-member-only`, and the `[data-tct-paywall]` section must come after the final unlocked article body and before newsletter/share.
