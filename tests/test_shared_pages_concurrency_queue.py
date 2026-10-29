"""Never silently cancel a scheduled Events or Missing Persons refresh.

GitHub's default workflow concurrency queue retains only one pending run.
When a News Update holds 'pages', a later Missing Persons run can cancel the
already-pending Events run even with cancel-in-progress: false.
The supported queue: max option retains up to 100 waiting runs in FIFO order
while preserving the existing single-writer lock.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = (
    ".github/workflows/update.yml",
    ".github/workflows/update-events.yml",
    ".github/workflows/update-missing-persons.yml",
)


def test_all_site_publishers_use_shared_non_cancelling_multi_pending_queue():
    for path in WORKFLOWS:
        workflow = (ROOT / path).read_text(encoding="utf-8")
        assert workflow.count('group: "pages"') == 1, path
        assert workflow.count("  cancel-in-progress: false") == 1, path
        assert workflow.count("  queue: max") == 1, path
        assert (
            'concurrency:\n  group: "pages"\n'
            '  cancel-in-progress: false\n  queue: max\n'
        ) in workflow, path
        assert workflow.index("  queue: max") < workflow.index("jobs:"), path


def test_events_and_missing_persons_still_use_their_existing_publish_guards():
    events = (ROOT / WORKFLOWS[1]).read_text(encoding="utf-8")
    missing = (ROOT / WORKFLOWS[2]).read_text(encoding="utf-8")
    for workflow in (events, missing):
        assert "for attempt in 1 2 3" in workflow
        assert "git push origin HEAD:main" in workflow
        assert "git reset --hard origin/main" in workflow
        assert "needs: update" in workflow
        assert "actions/deploy-pages@v4" in workflow
    # Preserve strict source-freshness validation; a transient FDLE 200 with
    # no independently verifiable county must stay red rather than publish stale.
    assert "python -u scripts/update_missing_persons.py" in missing
    assert "python scripts/update_missing_persons.py --validate-only" in missing
