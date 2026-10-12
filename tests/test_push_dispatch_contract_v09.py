from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FUNC = (ROOT / 'supabase/functions/push-dispatch/index.ts').read_text()
MIGRATION = (ROOT / 'supabase/migrations/202610120001_ios_push_dispatch_ledger.sql').read_text()
WORKFLOW = (ROOT / '.github/workflows/send-ios-news-alert.yml').read_text()
DEPLOY = (ROOT / '.github/workflows/deploy-ios-push-dispatch.yml').read_text()


def test_manual_sender_files_present_without_restricting_existing_tct_files():
    # CI runs inside the full TCT repository, not the small delta overlay.
    # Verify the sender's required files exist; do not compare the entire
    # repository to the overlay manifest (the previous test did this and failed
    # on every legitimate article, asset, workflow, and existing test).
    required = {
        '.github/workflows/deploy-ios-push-dispatch.yml',
        '.github/workflows/send-ios-news-alert.yml',
        'supabase/functions/push-dispatch/index.ts',
        'supabase/migrations/202610120001_ios_push_dispatch_ledger.sql',
        'scripts/configure_ios_push_dispatch.ps1',
        'docs/IOS_PUSH_SENDER_v09_SETUP.md',
        'tests/test_push_dispatch_contract_v09.py',
        'tests/test_push_dispatch_runtime_v09.mjs',
    }
    missing = sorted(path for path in required if not (ROOT / path).is_file())
    assert not missing, f"Missing push sender files: {missing}"

    # Both delivery and deployment workflows must remain manual-only.  They
    # should never launch automatically from editorial publishing or a timer.
    for content in (WORKFLOW, DEPLOY):
        assert '\non:\n  workflow_dispatch:' in '\n' + content
        assert '\n  push:' not in content
        assert '\n  schedule:' not in content
        assert '\n  workflow_run:' not in content


def test_send_requires_secret_flag_and_confirmation():
    assert 'x-tct-push-dispatch-key' in FUNC
    assert "TCT_PUSH_DISPATCH_KEY" in FUNC
    assert 'TCT_PUSH_SENDING_ENABLED' in FUNC
    assert "input.confirm !== 'SEND'" in FUNC
    assert 'LIVE_ENABLED' in FUNC
    assert 'action === \'preview\'' in FUNC


def test_no_apns_key_in_repo_workflow():
    assert 'TCT_APNS_P8_BASE64' in FUNC
    assert 'TCT_APNS_P8_BASE64' not in WORKFLOW
    assert 'TCT_APNS_P8_BASE64' not in DEPLOY
    assert 'TCT_PUSH_DISPATCH_KEY' in WORKFLOW
    assert 'permissions:' in DEPLOY and 'contents: read' in DEPLOY


def test_only_one_send_per_story_at_db_level():
    assert 'slug text primary key' in MIGRATION
    assert 'enable row level security' in MIGRATION
    assert 'revoke all' in MIGRATION
    assert 'range(0, MAX_DEVICES)' in FUNC
    assert 'MAX_DEVICES = 50' in FUNC
