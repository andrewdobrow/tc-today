# TCT v1.13.9.36 — Remove anchored monthly-free article banner

## Change
- Removed the anchored bottom “You’re reading your free article for this month” banner from the monthly free-article experience.
- Removal applies at every viewport size; there is no desktop or mobile fallback banner.
- The ordinary post-read subscription/paywall treatment remains in place.
- Mediavine ad slots and paid-member `mv-no-ads` behavior are unchanged.
- Removed the banner's JavaScript creation/scroll/dismiss logic and its unused CSS.
- Bumped membership assets to `1.13.9.36` so retained article shells are normalized to the banner-free JavaScript on the next Production/Update run.

## Regression protection
- Membership tests now assert the anchored free-article banner implementation is absent from both `membership.js` and `membership.css`.
