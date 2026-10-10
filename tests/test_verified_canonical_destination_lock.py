from tests.test_forward_publication_identity import _load_generate


def test_verified_canonical_cannot_be_restamped_to_unrelated_july_permalink():
    g = _load_generate()
    item = {'headline': 'Sheriff: Deputies Heard Kittens Crying Underground'}
    canonical = {'slug': '2026-10-08-hobe-sound-woman-accused-of-burying-cats-alive-says-she-thought-they-were-demons', 'editorial_story_id': 'cat-incident'}
    unrelated = {'slug': '2026-07-03-hobe-sound-community-raises-funds-for-man-whose-fiancee-died-in-monday-house-fir', 'editorial_story_id': 'house-fire'}
    proof = {'write_authorized': True, 'outcome': 'same_event_verified', 'proof_type': 'independent_event_evidence'}
    assert g._stamp_canonical_write_authorization(item, canonical, proof)
    assert g._stamp_canonical_write_authorization(item, unrelated, proof) is None
    assert item['_canonical_write_authorization']['canonical_slug'] == canonical['slug']
    assert item['_canonical_destination_conflict']['attempted_slug'] == unrelated['slug']


def test_repeated_stamping_of_same_canonical_is_allowed():
    g = _load_generate()
    item = {}
    target = {'slug': '2026-10-08-cat', 'editorial_story_id': 'cat'}
    proof = {'write_authorized': True, 'outcome': 'same_event_verified'}
    assert g._stamp_canonical_write_authorization(item, target, proof)
    assert g._stamp_canonical_write_authorization(item, target, proof)
    assert '_canonical_destination_conflict' not in item


def test_final_publication_barrier_holds_mismatched_destination():
    from pathlib import Path
    source = (Path(__file__).parents[1] / 'scripts' / 'generate.py').read_text()
    assert 'hold_without_overwrite_or_new_permalink' in source
    assert '_final_slug != _locked_slug' in source
    assert 'verified_canonical_destination_conflict' in source


def test_composition_keeps_original_destination_authority():
    g = _load_generate()
    item = {'headline': 'Earlier cat report'}
    canonical = {'slug': '2026-10-08-cat', 'editorial_story_id': 'cat'}
    proof = {'write_authorized': True, 'outcome': 'same_event_verified'}
    g._stamp_canonical_write_authorization(item, canonical, proof)
    assert g._replace_publication_payload_preserving_authority(item, {'headline': 'New sheriff update'})
    assert item['headline'] == 'New sheriff update'
    assert item['_canonical_write_authorization']['canonical_slug'] == canonical['slug']
    assert g._forward_publication_target_valid(item, None, '', '') == (False, 'verified_canonical_destination_mismatch')


def test_composition_cannot_retarget_to_unrelated_canonical():
    g = _load_generate()
    item = {}
    proof = {'write_authorized': True, 'outcome': 'same_event_verified'}
    g._stamp_canonical_write_authorization(item, {'slug': '2026-10-08-cat'}, proof)
    replacement = {}
    g._stamp_canonical_write_authorization(replacement, {'slug': '2026-07-03-fire'}, proof)
    assert not g._replace_publication_payload_preserving_authority(item, replacement)
    assert item['_canonical_write_authorization']['canonical_slug'] == '2026-10-08-cat'
    assert item['_canonical_destination_conflict']['attempted_slug'] == '2026-07-03-fire'


def test_legitimate_same_canonical_update_continues_after_composition():
    g = _load_generate()
    item = {'headline': 'Original cat coverage'}
    canonical = {'slug': '2026-10-08-cat', 'editorial_story_id': 'cat'}
    proof = {'write_authorized': True, 'outcome': 'same_event_verified'}
    g._stamp_canonical_write_authorization(item, canonical, proof)
    assert g._replace_publication_payload_preserving_authority(item, {'headline': 'New verified developments'})
    assert g._stamp_canonical_write_authorization(item, canonical, proof)
    assert not item.get('_canonical_destination_conflict')


def test_persistent_match_does_not_claim_success_when_retarget_is_rejected():
    g = _load_generate()
    item = {'headline': 'Cats buried alive', 'editorial_story_id': 'cat'}
    proof = {'write_authorized': True, 'outcome': 'same_event_verified'}
    g._stamp_canonical_write_authorization(item, {'slug': '2026-10-08-cat', 'editorial_story_id': 'cat'}, proof)
    assert g._stamp_canonical_write_authorization(item, {'slug': '2026-07-03-fire', 'editorial_story_id': 'fire'}, proof) is None
    assert item.get('_canonical_destination_conflict')
    assert g._forward_publication_target_valid(item, {'slug': '2026-07-03-fire'}, '', '') == (False, 'canonical_destination_conflict')
