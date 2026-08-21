# TCT v1.13.6.5 — Sonnet 5 Shadow Model Bake-Off

## Purpose

Measure whether Claude Sonnet 5 materially improves TCT's category-level writing and editorial decisions before changing the production model.

## Production behavior

No production model changes are made. `MODEL_ARTICLES` and `MODEL_SELECTION` remain `claude-sonnet-4-5`.

The bake-off is opt-in from the manual **Update Treasure Coast Today** workflow. The new `model_bakeoff` checkbox defaults to `false`.

When enabled:

1. normal Sonnet 4.5 category generation runs exactly as before;
2. after a successful live category response is parsed, TCT keeps an in-memory copy of that exact request packet and normalized model output;
3. the normal site build, caches, contracts, archives and static output finish first;
4. only then is the copied request packet sent to `claude-sonnet-5`;
5. Sonnet 5 output is written only to bake-off review artifacts and cannot enter publication state.

Categories served entirely from the persistent generation cache do not create a new model packet and therefore are not included in that run's bake-off. One or two runs with changing feeds should provide a representative sample without forcing live regeneration.

## Sonnet 5 comparison configuration

The first controlled comparison uses:

- model: `claude-sonnet-5`
- thinking: disabled
- max output tokens: 8,000
- identical system prompt, user prompt and source packet to the successful Sonnet 4.5 category request

Thinking is explicitly disabled because Sonnet 5 enables adaptive thinking by default while the current Sonnet 4.5 TCT path does not use thinking. This first test therefore isolates the newer model's direct structured writing/selection quality. The larger output ceiling provides headroom for Sonnet 5's newer tokenizer.

## Artifacts

A checked bake-off run writes:

- `data/model-bakeoff-review.md` — blind A/B review; model identities omitted and assignments vary by category.
- `data/model-bakeoff-answer-key.json` — open only after scoring the blind review.
- `data/model-bakeoff-report.json` — machine-readable full comparison and structural signals.
- `data/model-usage-report.json` — existing telemetry, now including Sonnet 5's actual token use and list cost.

The workflow also uploads all four files as a 14-day GitHub Actions artifact named `tct-model-bakeoff-<run_id>`.

## Cost observability update

`model_usage.py` now prices Sonnet 5 at the current standard Claude API rates:

- base input: $2 / MTok
- 5-minute cache write: $2.50 / MTok
- 1-hour cache write: $4 / MTok
- cache read: $0.20 / MTok
- output: $10 / MTok

Anthropic's current pricing documentation says the previously announced September increase will not occur; $2/$10 is now the standard Sonnet 5 base input/output price.

## Validation

- workflow-equivalent pytest: **907 passed**, 43 existing warnings
- package validation: **37 modules / 119 exports**
- generator runtime hotfix guard: **PASS**
- false-jurisdiction source guard: **PASS**
- workflow YAML parse: **PASS**
- generator import with production models unchanged and bake-off default off: **PASS**
