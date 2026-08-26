# v1.13.6.7o Review Guide

Apply this overlay directly to the current repository that already received 6.7n.
No earlier overlay needs to be re-applied afterward.

Expected Test Editorial Engine result:
- 1,004 tests in the CI-equivalent suite (excluding the workflow's two standard ignored files)
- zero failures

The two previously failing tests should now use an older exact-source archive receipt to prove
publisher timestamp retouching. This is deliberate: without prior receipt evidence, a fresh RSS
timestamp plus prior-day event language cannot reliably distinguish a newly published next-day
report from a publisher retouch.

After Test Editorial Engine is green, run one production cycle and review terminal permalink
authority / semantic publication diagnostics before scoring the Sonnet bakeoff.
