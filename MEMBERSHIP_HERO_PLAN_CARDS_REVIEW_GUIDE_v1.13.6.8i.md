# v1.13.6.8i review guide

Review `/subscribe.html` on desktop and mobile.

Expected desktop hero:
- Editorial headline and deck remain on the left.
- Right column contains two compact cards, Monthly above Annual.
- Monthly displays `$1`, `for your first month`, `Then $4.99/month`, and a `Choose Monthly` button.
- Annual displays `$49/year`, `Best value`, and a `Choose Annual` button.
- Both buttons begin the existing Stripe checkout flow directly; no scrolling is required.
- The old `3 counties / Ad-free / Independent` sidebar is gone.

Expected responsive behavior:
- Tablet: the two plan cards can sit side-by-side below the hero copy.
- Mobile: cards stack in one column.

The full plan comparison farther down the page should remain unchanged.
