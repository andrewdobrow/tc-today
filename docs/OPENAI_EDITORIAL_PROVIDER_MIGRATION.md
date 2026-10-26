# TCT Claude → OpenAI Editorial Provider Swap

## Scope

This change replaces only the **AI service** used by TCT. It does **not** replace, refactor, or remove the editorial engine, story registry, source gathering, material-update checks, deduplication, canonical article protection, homepage pipelines, publication gates, caches, or schedules.

A single transport adapter (`tct_engine/openai_editorial_client.py`) translates existing Anthropic-style message calls to OpenAI's Responses API. Existing TCT editorial functions continue using `client.messages.create` and `client.with_options`, their existing prompts, model responses and deterministic post-generation checks. The TCT model-usage tracker stays wrapped around that interface.

## Models and routing

- Default behavior: `TCT_LLM_PROVIDER=anthropic`, Sonnet 5 as currently configured. This is the **safe, unchanged state after merging this PR**.
- OpenAI activation: repository variable `TCT_LLM_PROVIDER=openai`; the OpenAI model is `gpt-6.1-sol` for article generation, source selection, classification, incident review, semantic identity and material-update calls. The assignment editor defaults to OpenAI when provider=openai. All other TCT code stays in place.
- The existing `TCT_ASSIGNMENT_EDITOR_MODEL` override can still change the requested editor model *label*, but the provider flag determines the actual API provider. Do not set conflicting model overrides in a live run.
- **Immediate rollback:** repository variable `TCT_LLM_PROVIDER=anthropic`, then run the existing Test Editorial Engine first and Update only after tests pass. No code rollback required.
- No automatic Claude fallback during an OpenAI editorial or quality-check failure. Original TCT fail-closed rules remain authoritative. The reversible provider variable is the explicit fallback.
- The historic/manual model bake-off remains separate; the production provider flag does not start it or invoke duplicate calls.

## GitHub configuration

The existing `.github/workflows/update.yml` now installs OpenAI's Python SDK and passes `OPENAI_API_KEY` from **GitHub Actions secrets** along with the repository variable `TCT_LLM_PROVIDER`. Never commit or print keys.

1. **Do not activate during PR validation.** The default remains Anthropic even after a merge.
2. Confirm repository Actions secret `OPENAI_API_KEY` is populated (the previous paid comparisons likely used the secret, but the configuration must be checked).
3. Run the existing **Test Editorial Engine** workflow on the merged main branch.
4. Set **Settings → Secrets and variables → Actions → Variables → New repository variable**: `TCT_LLM_PROVIDER` = `openai` only when prepared to run a **live** OpenAI-backed editorial update.
5. Run the existing **Update** workflow. Review source fidelity, category assignments, article copy, canonical permalinks, updates, duplicate suppressions, timing, and the model-usage report before leaving OpenAI active for scheduled updates.
6. If a quality or compatibility problem occurs, set the variable to `anthropic` and keep the existing safeguards; run existing tests before next publishing update.

**No configuration change is made automatically by this PR.** The rollout is controlled in GitHub, not via a new workflow or a rewritten generator.

## Provider conversion

The adapter accepts the message shapes currently used by TCT:

- `system` as text or Anthropic text blocks, preserving *exact text* and role boundaries;
- `messages` as user/assistant text;
- `max_tokens` translated to bounded `max_output_tokens`;
- `thinking` (Anthropic-only) excluded from OpenAI transport, with bounded reasoning effort selected based on the output size;
- `with_options(timeout, max_retries)` preserved via the OpenAI SDK;
- response `model`, `content[0].text`, `usage` and `stop_reason` normalized to the interface existing code uses.

Unsupported tool calls, streaming calls, content blocks or incomplete/empty Responses fail rather than silently switching providers or fabricating output. OpenAI's own prompt caching is accounted for without double-counting cached tokens.

The TCT model-usage report identifies the actual provider and estimates costs with provisional model prices based on the paid bake-offs; invoice amounts may differ. The report deliberately stores no prompts or article text.

## Limitations and production safety

The historical blind-writing wins justify a controlled migration, but they were not equivalent to a full integrated material-update/canonical continuity test. This adapter preserves the *existing code* that handles those workflows rather than changing policy.

No paid API calls or live publication are part of the PR. Automated tests use offline model/SDK stubs. Run one supervised Update after explicit activation; audit failures before relying on the regular schedule. Production correctness must be judged by evidence from an actual OpenAI-backed run, not merely passing adapter unit tests.

**Release checklist:** offline transport tests pass; existing full editorial suite passes; no publication path or canonical identity code altered; repository variable remains absent/default (Anthropic) until intentional activation; rollback instructions documented.
