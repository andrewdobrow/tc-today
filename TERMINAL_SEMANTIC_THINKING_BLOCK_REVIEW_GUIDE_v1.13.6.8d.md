# Review guide — v1.13.6.8d

After deployment, run Test Editorial Engine and then one Generate News production run.

Validate in `data/semantic-publication-gate.json`:
1. No terminal decision contains `"'ThinkingBlock' object has no attribute 'text'"`.
2. `terminal_permalink_*` model calls can return validated `new_story`, `duplicate_use_existing_canonical`, `update_existing_canonical`, or genuine evidence-based `hold` decisions.
3. A genuine model/API failure still fails closed to HOLD.
4. If a first-pass decision is a validated HOLD, the existing single focused resolution pass remains eligible.
