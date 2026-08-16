# Subscriber Chrome Review Guide — v1.13.6.2

Verify with one active subscriber and one signed-out browser.

1. Signed-out homepage: Subscribe and Sign in remain visible; membership promo card remains visible.
2. Signed-in active/trialing subscriber homepage: header reads `Welcome, <first name>` and the membership promo card is absent.
3. Signed-in subscriber article: full article unlock still works and header welcome state is shown.
4. Signed-in subscriber subscribe page: plan cards remain hidden by existing account logic and welcome header is shown.
5. Sign out without reloading: acquisition header/card return.
6. Existing subscriber whose first name cannot be recovered: header reads `Welcome, subscriber`; entitlement must still work.
7. Confirm protected article content is still retrieved only through `protected-article`.
