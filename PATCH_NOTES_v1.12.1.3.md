# TCT v1.12.1.3 — Newsletter Sticky Top Layer

## Problem

Kit's sticky-bar form was injected inside an additional positioned wrapper. The
previous release raised the inner `.formkit-sticky-bar`, but the wrapper itself
remained in a lower stacking context beneath TCT's sticky masthead. Only a thin
strip of the newsletter bar remained visible on desktop and mobile.

## Correction

- Detect the actual Kit sticky form after asynchronous injection.
- Walk to the outermost injected element immediately beneath `<body>`.
- Promote that outer wrapper into a dedicated fixed viewport layer.
- Neutralize wrapper transforms, clipping, bottom positioning, and inherited
  stacking contexts.
- Use a deterministic compact height: 72px desktop and 58px mobile.
- Offset the complete TCT masthead and article reading-progress indicator below
  the visible bar.
- Continue removing all reserved space automatically when Kit hides or closes
  the form.

## Scope

This is a presentation-only correction. Newsletter UIDs, custom articles,
editorial identity behavior, publication logic, and the homepage/category
newsletter layout are unchanged.
