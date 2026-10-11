from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FUNC = (ROOT / 'supabase/functions/push-dispatch/index.ts').read_text()
MIGRATION = (ROOT / 'supabase/migrations/202610120001_ios_push_dispatch_ledger.sql').read_text()
WORKFLOW = (ROOT / '.github/workflows/send-ios-news-alert.yml').read_text()
DEPLOY = (ROOT / '.github/workflows/deploy-ios-push-dispatch.yml').read_text()


def test_no_publish_pipeline_or_other_function_mutations():
    # Scope invariant: these are the only files allowed in this overlay.
    files = {str(p.relative_to(ROOT)) for p in ROOT.rglob('*') if p.is_file() and not any(part.startswith('.') and part != '.github' or part == '__pycache__' for part in p.relative_to(ROOT).parts)}
    assert files == {
        '.github/workflows/deploy-ios-push-dispatch.yml',
        '.github/workflows/send-ios-news-alert.yml',
        'supabase/functions/push-dispatch/index.ts',
        'supabase/migrations/202610120001_ios_push_dispatch_ledger.sql',
        'scripts/configure_ios_push_dispatch.ps1',
        'docs/IOS_PUSH_SENDER_v09_SETUP.md',
        'tests/test_push_dispatch_contract_v09.py',
        'tests/test_push_dispatch_runtime_v09.mjs',
    }


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
