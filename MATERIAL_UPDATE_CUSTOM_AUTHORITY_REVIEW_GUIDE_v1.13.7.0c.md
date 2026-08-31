# v1.13.7.0c production review guide

After Test Editorial Engine is green, run Generate News once and verify:

1. Registry preflight converges within the existing 16-pass ceiling.
2. A same-story material update that paraphrases source wording is not falsely held as `new_development_missing` when the lead contains a semantic-gate novel fact.
3. For a custom canonical, an unverified feed copy is still suppressed and cannot mint a second URL.
4. If a newer source is validated as a material update to a custom canonical, the existing custom slug is retained and the page is refreshed in place.
5. `data/semantic-publication-gate.json` should distinguish genuine composition holds from successful material updates; do not require zero holds globally.
