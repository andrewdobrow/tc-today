# TCT v1.13.6.3 — model usage and cost observability

## Scope

Behavior-neutral production telemetry only. This release does **not** change the configured Claude model, prompts, story selection, category rules, ranking, duplicate handling, article generation, publication gates, membership behavior, or page rendering.

## What changed

- Added `tct_engine/model_usage.py`, a transparent wrapper around the production Anthropic client.
- Every Anthropic `messages.create()` response now contributes usage metadata to `data/model-usage-report.json`.
- The report records raw base-input, prompt-cache write, prompt-cache read, total input-context and output token counts so the exact workload can be repriced against other models later.
- Calls are grouped by model, call site and workload class. The large category request is intentionally labeled `mixed_generation_and_selection` because the current prompt both chooses stories and writes article copy in one call.
- Current Claude Sonnet 4.5 standard/global list cost is estimated from Anthropic's 2026-06-30 list pricing: $3/M base input, $3.75/M 5-minute cache writes, $6/M 1-hour cache writes, $0.30/M cache reads, and $15/M output.
- The production log prints a compact total and per-workload cost summary after the generator exits.
- Failed model requests are counted without inventing token usage when the provider returns no usage metadata.

## Safety properties

- No prompts, source article text, generated article text, API keys, or user data are written to the telemetry report.
- Telemetry failures are fail-open: they cannot turn a successful publication run into a failed run or mask the generator's original exception.
- `with_options()` clients remain instrumented, which covers timeout-bounded category and semantic calls.
- Unknown/future models retain their raw token counts even when no price is registered, allowing later repricing.

## Production review

After the next **Update Treasure Coast Today** run, inspect `data/model-usage-report.json` and the `Model usage:` lines in the workflow log. Those numbers provide the real workload needed for a model bake-off and cost projection before changing TCT's production model.
