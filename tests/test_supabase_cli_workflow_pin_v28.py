from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
UPDATE = ROOT / ".github" / "workflows" / "update.yml"
BACKEND = ROOT / ".github" / "workflows" / "deploy-membership-backend.yml"
PIN = 'SUPABASE_CLI_VERSION: "2.117.0"'


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_production_workflow_does_not_use_rate_limited_setup_cli_latest():
    text = _text(UPDATE)
    assert "supabase/setup-cli" not in text
    assert "version: latest" not in text
    assert PIN in text
    assert 'npm install --prefix "$cli_root"' in text
    assert '"supabase@${SUPABASE_CLI_VERSION}"' in text


def test_supabase_cli_preflight_happens_before_expensive_generation():
    text = _text(UPDATE)
    preflight = text.index("- name: Preflight pinned Supabase CLI")
    generation = text.index("- name: Generate news")
    assert preflight < generation
    assert "uses: actions/setup-node@v6" in text
    assert "node-version: '24'" in text


def test_manual_backend_deploy_uses_same_pinned_cli_path():
    text = _text(BACKEND)
    assert "supabase/setup-cli" not in text
    assert "version: latest" not in text
    assert PIN in text
    assert 'npm install --prefix "$cli_root"' in text
    assert '"supabase@${SUPABASE_CLI_VERSION}"' in text
    assert "supabase functions deploy --use-api" in text
