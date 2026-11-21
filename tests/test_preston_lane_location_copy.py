"""Regression for the editor's exact Port St. Lucie location correction."""
import json

from scripts.reconcile_preston_lane_location import NEW, OLD, SLUG, reconcile_archive


def test_exact_story_archive_teaser_is_corrected_and_second_pass_is_noop(tmp_path):
    path = tmp_path / "archive.json"
    other = {"slug": "unrelated", "teaser": "Other reporting remains unchanged."}
    original = [
        {"slug": SLUG, "headline": "Road collapse", "teaser": OLD + ", leaving a hole"},
        other,
    ]
    path.write_text(json.dumps(original, indent=2) + "\n", encoding="utf-8")
    assert reconcile_archive(path) is True
    updated = json.loads(path.read_text(encoding="utf-8"))
    assert updated[0]["teaser"] == NEW + ", leaving a hole"
    assert updated[1] == other
    contents = path.read_text(encoding="utf-8")
    assert reconcile_archive(path) is False
    assert path.read_text(encoding="utf-8") == contents


def test_no_unrelated_archive_location_is_rewritten(tmp_path):
    path = tmp_path / "archive.json"
    data = [{"slug": "another", "teaser": OLD + ", leaving a hole"}]
    path.write_text(json.dumps(data) + "\n", encoding="utf-8")
    assert reconcile_archive(path) is False
    assert json.loads(path.read_text(encoding="utf-8")) == data


def test_existing_editor_correction_is_preserved(tmp_path):
    path = tmp_path / "archive.json"
    data = [{"slug": SLUG, "teaser": NEW + ", leaving a hole"}]
    path.write_text(json.dumps(data) + "\n", encoding="utf-8")
    assert reconcile_archive(path) is False
    assert json.loads(path.read_text(encoding="utf-8")) == data
