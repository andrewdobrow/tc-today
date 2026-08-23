# Review Guide — v1.13.6.7e Universal Article Paywall Policy

## Goal
Verify that TCT no longer grants subject-matter-based public-service exemptions from the membership paywall.

## Production checks

After applying the overlay and running the membership-enabled production workflow:

1. Open the Flock homicide article that previously appeared fully free because it mentioned `locating missing children`.
2. Confirm the article now shows the normal TCT preview/paywall treatment for a non-member.
3. Confirm the page does not expose the protected remainder in public HTML.
4. Confirm an entitled member can still retrieve the full article through the protected-content flow.
5. Search the workflow log for `public-service free`; the old exemption counter should no longer appear.
6. Confirm the workflow still completes protected-content export/sync successfully.

## Regression intent

Public-service subject matter is no longer membership policy. The following are treated like any other normal TCT article when they meet the standard content-length split contract:

- Amber Alerts / missing-child stories
- mandatory evacuation stories
- hurricane/storm-surge warnings
- boil-water notices
- emergency shelter information
- emergency bridge closures
- ordinary stories that only mention any of those concepts

## Not changed

This increment does not alter:

- the minimum article-length requirement needed to create a safe preview/protected split;
- redirect/noindex pages;
- non-article pages;
- member entitlement verification;
- Stripe or Supabase configuration;
- article/story identity;
- editorial/model selection or assignment-editor bakeoff behavior.
