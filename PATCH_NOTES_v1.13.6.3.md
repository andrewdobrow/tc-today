# TCT v1.13.6.3 — generator lineage reconciliation

## Root cause

The Aug. 19 failure chain was not a sequence of independent production defects. A later root-ready overlay replaced the entire `scripts/generate.py` with a copy built from an older repository snapshot. That silently rolled back generator-side work from releases that had already been applied, while their tests, supporting modules, CSS/JS, and release artifacts remained in the repository.

The repository itself proves the divergence:

- `RELEASE_MANIFEST_v1.13.6.2.sha256` records the pre-clobber generator hash `912795e7be5faf8d0fb5200c3073e4d2e0eba000084b4649f58b4630cb4fec21`.
- The uploaded Aug. 19 repository's `scripts/generate.py` matched the later v1.13.6.1e overlay byte-for-byte at `b01ac0654a4e987327607c05a354114737b79971bb87b5f91e62315ce41c4ffb`.
- The same repository still contained the newer v1.13.6.2 subscriber-chrome files/tests and the Martin cocaine regression modules/tests, proving only the generator side had been rolled back.
- Historical release suffixes `1c`, `1d`, and `1e` had also been reused for unrelated patches, making lineage ambiguous.

## Reconciliation

This release starts from the user's uploaded repository as the sole authority and restores the generator responsibilities that its surviving release contracts require:

1. **v1.13.6.2 subscriber chrome**
   - restores the hidden `Welcome, subscriber` header control (`data-membership-welcome`);
   - restores sitewide membership prepaint/client injection on normalized pages;
   - continues to use the existing server-authoritative entitlement path.

2. **Martin County Operation Beneath the Surface duplicate protection**
   - a drug seizure no longer becomes `animal-case` merely because the source says `seized`;
   - narcotics coverage can emit `drug-case` evidence;
   - restores the deterministic verified-production fallback for the Aug. 14/15/16 duplicate URLs;
   - the general semantic/structured identity gate still runs first.

3. **All Aug. 19 stabilization work is preserved**
   - exact-headline runtime fix;
   - forward publication identity reconciliation;
   - registry pressure serialization;
   - final live-category identity alignment and self-diagnosing failure output.

## Prevention

Adds `tests/test_generator_release_contract_coherence.py`. Its purpose is explicitly to fail when a stale whole-file generator overlay preserves one hotfix while silently erasing another active release contract.

Future generator overlays must be built from the newest uploaded production repository, and release suffixes must not be reused for unrelated changes.
