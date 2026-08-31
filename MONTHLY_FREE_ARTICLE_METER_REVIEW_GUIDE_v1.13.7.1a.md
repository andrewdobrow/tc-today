# v1.13.7.1 review guide — Monthly free article meter

After Test Editorial Engine is green, run Generate News once.

## Expected first production run

1. Workflow probe reports either:
   - `Monthly free-article meter capability is current.`, or
   - `Legacy protected-article function detected; metered function will be deployed automatically.`
2. Protected-content snapshot/preparation/sync still complete normally.
3. Open an article in a signed-out browser with TCT site storage cleared:
   - the complete article should load;
   - there should be no paywall in the middle of the story;
   - after the final paragraph, the card should say `You've read your free article this month.`
4. Open a different protected article:
   - only the teaser should be visible;
   - the paywall headline should say `Continue reading Treasure Coast Today for just $1.`;
   - the body should explain `You've read your free article this month.`;
   - monthly remains `$1 for your first month`, then `$4.99/month`;
   - annual remains `$49/year`.
5. Reopen the first article:
   - it should still open fully.
6. Sign in as an active subscriber:
   - protected articles should remain unlimited and the meter card should disappear.

## Intentional limitation

The allowance is browser-storage based. Clearing site data or using a separate private browser can claim another free article. This is deliberate to avoid mandatory registration and invasive fingerprinting.
