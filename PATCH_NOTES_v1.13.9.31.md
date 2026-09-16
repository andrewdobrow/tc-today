# TCT v1.13.9.31 — Mediavine membership targeting and ad placement

- Paid subscribers now receive the `mv-no-ads` body class after verified entitlement. Returning paid subscribers also receive the class during the existing prepaint hint path so Mediavine can exclude them as early as possible.
- Adds the Mediavine-requested `mv-leader` slot immediately between the public article preview/fade treatment and the membership paywall.
- Reserves at least 90px for the leaderboard on mobile and 250px on desktop to prevent CLS and preserve broader desktop creative eligibility.
- Suppresses the reserved leaderboard slot for paid subscribers so ad-free members do not see an empty ad gap.
- Changes the article sidebar from sticky to static on desktop so Mediavine can target sidebar ads. Mobile sidebar behavior remains static.
- Adds `No ads` as an explicit benefit on the article paywall and both plans on `/subscribe.html`.
- Normalizes existing membership prepaint scripts during page preparation so retained pages receive the current `mv-no-ads` behavior rather than keeping stale inline code.
- No changes to subscription pricing, Stripe billing, entitlement authority, monthly-free metering, editorial generation, registry repair, or ad rail placement.
