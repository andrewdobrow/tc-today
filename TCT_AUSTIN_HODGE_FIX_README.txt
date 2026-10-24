TCT — Austin Hodge single custom article + weekend test repair (October 24, 2026)

Extract this ZIP at the ROOT of the tc-today repository and allow the four repository files to be added/replaced.

CHANGES
- custom_articles.json: contains ONLY the October 24 Austin Hodge line-of-duty death article. image_url remains empty.
- tests/test_weekend_guide_expiration.py: validates actual expiration behavior with an isolated historical fixture; does not require the weekend guide in today's editor queue.
- tests/test_weekend_top_five_oct_24_25_2026.py: validates the previous weekend guide's recorded content without requiring it to remain queued.
- tests/fixtures/weekend_top_five_oct_24_25_2026.json: historical test input only; not a live article, not processed by the publishing queue.

CONFIRMATION
- Exactly one item in custom_articles.json.
- The active item is St. Lucie County Firefighter-Paramedic Austin Hodge Dies in Line of Duty.
- No edits to scripts/generate.py or live article archives.
- Isolated tests: 8 passed.
- Full editorial pytest tests directory against the provided repository snapshot (Python 3.13): 1734 passed, 4 skipped, 10 subtests passed. CI uses Python 3.11 and must be run after push.
- The editor queue is always replaced by the newly requested custom article; historical fixtures must not be copied into the active custom_articles.json file.

WORKFLOW
Commit/push and run Test Editorial Engine. If green, run Update Treasure Coast Today.
