# v1.13.5.1 — Membership Launch Banner Cleanup

Launch-candidate correction on top of v1.13.5.0.

- Removes the legacy “Support Treasure Coast Today” article banner when membership UI is enabled.
- Keeps the existing support banner unchanged while membership remains dark-launched.
- Removes the banner from retained historical direct article HTML at launch, not only newly generated articles.
- Prevents the recent-article support-banner migration from putting the banner back during a membership launch run.
- Updates article presentation validation so a banner is no longer required after membership launches.
- Keeps header Subscribe, article paywall, Stripe checkout, entitlement, admin bypass, and all other v1.13.5.0 behavior unchanged.
