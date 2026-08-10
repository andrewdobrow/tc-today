# TCT v1.13.5.7 — Signed-in member no-flash article loading

This increment removes the brief subscription/paywall-card flash that verified members could see while a new article restored the Supabase session and rechecked entitlement.

## What changes

- A successful server-side entitlement check stores a presentation-only browser hint: `tct_member_entitled_hint=1`.
- Paywalled article pages receive a tiny synchronous `<head>` script that reads that hint before first paint and adds `tct-member-preverified` to the document root.
- While that class is present, the anonymous-reader paywall/fade treatment is suppressed and the teaser is shown without its fade mask.
- The normal Supabase `membership-status` call still runs on every article. The hint never grants access to protected article text.
- Protected content is still fetched only after `status.entitled` is confirmed by the server-side membership function.
- If the session is gone, entitlement is definitively inactive, or the reader signs out, the hint is cleared and the normal paywall is restored.
- If the protected-content fetch fails, the prepaint suppression is removed so the existing error state remains visible rather than leaving a truncated article with no explanation.
- Membership JS/CSS references are normalized to `?v=1.13.5.7` on re-prepared pages so browsers do not keep pre-fix assets from cache.

## Security boundary

The browser hint is visual only. Editing or forging localStorage can hide the sales card temporarily, but cannot retrieve member content. Full article text remains outside public HTML and is returned only by the entitlement-checked `protected-article` Edge Function.

## Not changed

- Stripe checkout or billing
- Supabase subscription records
- session lifetime
- Kit newsletter forms/copy
- teaser character budget or fade design for signed-out readers
- stale-story, duplicate, Top Stories, or editorial ranking behavior

## Validation

- Workflow-equivalent pytest suite: 857 passed
- Membership-focused regression suite: 60 passed
- Package validation: 35 modules / 119 exports
- `membership.js` syntax check: passed
- Python compile check: passed
