# Registry Split Negative Identity — v1.13.7.0b Review Guide

After applying this overlay:

1. Run **Test Editorial Engine**.
2. The registry preflight should no longer fail with `did not converge within 16 passes` for the split/remerge cycle.
3. Expected test result: **1,053 passed**.
4. If green, run **Generate News** once. The production preflight may persist a repaired registry because the real tracked registry, unlike the test workflow's temporary copy, is normalized in place.
5. Verify the run reaches package validation/tests/generation rather than repeatedly creating and swallowing fresh timeline-split story IDs.

Do not raise the fixed-point pass ceiling. If another non-convergence appears after this patch, preserve the exact `Last merges:` output and inspect it as a different repair-authority defect.
