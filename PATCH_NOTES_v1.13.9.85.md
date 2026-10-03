# TCT v1.13.9.85 — Paywall ad-free access copy

Apply on top of **v1.13.9.84**.

## Change

The paywall subhead under **Keep reading** now reads exactly:

> Get unlimited, ad-free access to every story.

This replaces:

> Get full access to every story

## Retained-page behavior

`tct_engine/membership_paywall.py` also normalizes the previous subhead whenever membership assets are refreshed. This ensures already-paywalled retained article pages converge to the new wording on a normal production run without changing article publication dates or requiring an editorial story rewrite.

## Scope

- No pricing changes.
- No paywall layout changes.
- No article-body changes.
- No publication timestamp changes.
- No change to membership entitlement or advertising-control logic.
- No change to Bunny image handling.

## Validation

- Focused membership/paywall suite: **79 passed**.
- Production-equivalent test suite: **1,488 passed**, 0 failed.
- Package validation: **42 modules imported / 123 public exports verified**.
- Rendered current and retained paywall copy verified locally.
