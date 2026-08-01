# Newsletter Responsive Presentation Review Guide — v1.12.1.4

## Desktop checks

1. Open a private desktop browser window wider than 680px.
2. Confirm the Kit sticky bar appears above the TCT masthead.
3. Confirm the logo, navigation and article reading-progress line remain fully visible below it.
4. Confirm the mobile modal does not appear.
5. Confirm the category inline form remains beneath the hero and Latest News spans the full right column.

## Mobile checks

1. Open a private browser window at 680px or narrower.
2. Confirm no sticky newsletter strip appears and the TCT masthead starts at the top of the viewport.
3. Confirm Kit modal `be625cadfe` appears according to its Kit display rules.
4. Confirm the modal fits within the viewport, scrolls internally if needed and has an accessible close control.
5. Confirm the inline category/article form remains available after the modal is dismissed.

## Kit dashboard checks

- Sticky form `4edef44197`: desktop display rules may remain enabled; TCT does not load it on mobile.
- Modal `be625cadfe`: configure mobile-friendly timing and frequency in Kit.
- Recommended frequency: no more than once every seven days after dismissal.
