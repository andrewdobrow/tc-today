"""Stop broken shared JavaScript from disabling mobile navigation and Kit embeds."""

from pathlib import Path
import shutil
import subprocess

import pytest

from scripts.replace_header_app_store import replace_header_promo, CSS_ASSET_VERSION

ROOT = Path(__file__).resolve().parents[1]


def test_main_javascript_parses_before_any_deployment():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is not available in this test environment")
    result = subprocess.run(
        [node, "--check", str(ROOT / "main.js")],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_donation_url_normalization_uses_valid_trailing_slash_regex():
    js = (ROOT / "main.js").read_text(encoding="utf-8")
    assert r'url.pathname.replace(/\\/+$/, "")' in js
    assert 'isDonationPageLink' in js


def test_stale_main_javascript_versions_are_refreshed_for_all_pages():
    old = ('<html><body><header class="site-masthead"></header>'
           '<script src="/main.js?v=1.13.9.123"></script></body></html>')
    current = replace_header_promo(old)
    assert f'/main.js?v={CSS_ASSET_VERSION}' in current
    assert replace_header_promo(current) == current


def test_all_deploy_jobs_check_js_syntax():
    for path in (
        ".github/workflows/update.yml",
        ".github/workflows/update-events.yml",
        ".github/workflows/update-missing-persons.yml",
    ):
        workflow = (ROOT / path).read_text(encoding="utf-8")
        deploy = workflow.split("\n  deploy:", 1)[1]
        assert "node --check main.js" in deploy, path
        assert deploy.index("node --check main.js") < deploy.index("Upload artifact"), path
