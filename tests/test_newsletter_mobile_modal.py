from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_mobile_modal_is_not_hardcoded_into_generated_page_footer():
    source = (ROOT / "scripts" / "generate.py").read_text(encoding="utf-8")
    assert "be625cadfe" not in source


def test_mobile_modal_is_loaded_only_by_the_responsive_runtime_branch():
    js = (ROOT / "main.js").read_text(encoding="utf-8")
    mobile_block = js.index('mobile: {')
    modal_uid = js.index('uid: "be625cadfe"', mobile_block)
    modal_src = js.index(
        'src: "https://treasure-coast-today.kit.com/be625cadfe/index.js"',
        modal_uid,
    )
    selector = js.index(
        'const config = mobileQuery.matches ? embeds.mobile : embeds.desktop'
    )
    assert mobile_block < modal_uid < modal_src < selector


def test_sticky_layer_runtime_returns_without_offset_on_mobile():
    js = (ROOT / "main.js").read_text(encoding="utf-8")
    start = js.index("function syncStickyBarLayer()")
    end = js.index("const form = findStickyForm();", start)
    mobile_guard = js[start:end]
    assert "if (mobileQuery.matches)" in mobile_guard
    assert 'root.classList.remove("kit-sticky-visible")' in mobile_guard
    assert 'root.style.setProperty("--kit-sticky-height", "0px")' in mobile_guard
    assert "return;" in mobile_guard
