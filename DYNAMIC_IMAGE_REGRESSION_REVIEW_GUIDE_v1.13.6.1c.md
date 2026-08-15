# v1.13.6.1c Review Guide

This release corrects a mutable-state regression test only.

Expected behavior:
1. The historical Ethan Boyd article keeps its selected image in the override ledger, archive record, article hero, Open Graph metadata, and Twitter metadata.
2. If the article appears on the current homepage, every image-bearing placement must use the selected image.
3. If the article appears in the current RSS feed, that feed item must use the selected image.
4. The test must not require an older article to remain indefinitely on the homepage or in a rolling RSS feed.
5. No generator or permalink behavior changes are included.
