# TCT v1.13.6.8d — Terminal Semantic Thinking-Block Compatibility

## Root cause
A production terminal-permalink Sonnet 5 response contained a non-text `ThinkingBlock` before the JSON `TextBlock`. The semantic publication gate assumed `response.content[0].text`, raised `'ThinkingBlock' object has no attribute 'text'`, and correctly but unnecessarily failed closed to HOLD. Because the first pass had status `model_error` rather than a validated HOLD, the focused resolution pass did not run.

## Fix
- Add a response-text extractor that iterates all Anthropic content blocks and joins only blocks that expose `.text`.
- Use it in both initial semantic adjudication and the focused terminal resolution call.
- Preserve fail-closed HOLD behavior for genuine API/model/parser failures.
- Add regressions reproducing ThinkingBlock -> TextBlock responses for both passes.
- Repair the stale 6.8c footer regression assertion so the CI contract matches the intended compact `$1 first month` CTA.

## Live behavior changed
Only terminal semantic response parsing. No ranking, source retrieval, membership billing, or publication policy thresholds changed.
