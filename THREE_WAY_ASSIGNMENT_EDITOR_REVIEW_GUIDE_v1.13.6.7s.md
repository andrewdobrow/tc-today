# v1.13.6.7s Production Review Guide — Three-Way Assignment Editor Bakeoff

## Run configuration

Use **Generate News** manually:

- Assignment editor shadow: **ON**
- Legacy model bakeoff: **OFF**

The live publisher remains on the normal production path.

## Confirm in the log

Look for:

- `editors=claude-sonnet-5,claude-opus-5`
- `writer=claude-sonnet-4-5-20250929`
- `comparison=three-way-final-pipeline-aligned`
- one Sonnet 5 result and one Opus 5 result per queued category
- final line reporting scoreable categories / shadow failures

## Score in this order

1. Open `assignment-editor-shadow-review.md` first.
2. Score A / B / C / Tie across all 11 newsroom dimensions.
3. Do **not** open the answer key until scoring is recorded.
4. Open `assignment-editor-shadow-answer-key.json` only after blind scoring.
5. Use `assignment-editor-shadow-report.json` to diagnose *why* a path won or lost.

## Integrity checks

For every challenger path confirm:

- final source mapping is valid;
- no unexplained `blocked_source_integrity_rewrites` or mismatches exist;
- any challenger failure makes that category unscoreable;
- raw and final outputs are kept separate in the machine report.

## What this experiment answers

The writer is deliberately held constant at Sonnet 4.5. The useful question is therefore not “which model writes prettier copy?” It is:

**Does Opus 5 make materially better newsroom assignment decisions than Sonnet 5 and current production when all three are subjected to the same final publication rules?**
