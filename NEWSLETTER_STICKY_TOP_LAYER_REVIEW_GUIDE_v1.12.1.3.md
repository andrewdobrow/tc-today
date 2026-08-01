# Newsletter Sticky Top Layer Review Guide — v1.12.1.3

## Desktop

1. Open the homepage in a private window.
2. Confirm the complete Kit bar is visible at the top of the viewport.
3. Confirm the TCT logo masthead begins immediately below it.
4. Scroll and confirm both the bar and masthead remain visible without overlap.
5. Close the Kit bar and confirm the masthead returns to the top with no gap.

## Mobile

1. Open the homepage at a viewport below 680px.
2. Confirm the bar is 58px tall and shows the email field and Subscribe button.
3. Confirm the full TCT mobile masthead begins below the bar.
4. Confirm neither form control is clipped or covered.
5. Close the bar and confirm the page removes the reserved space.

## Regression checks

- Inline newsletter remains beneath each homepage/category hero.
- Latest News continues beside the hero-plus-newsletter stack on desktop.
- Article inline newsletter remains between the article body and share controls.
- Sticky and inline Kit embeds use separate UIDs and initialize once each.
