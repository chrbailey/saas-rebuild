"""Static workspace UX contracts that do not require a browser test runner."""

from conftest import REPO_ROOT


def test_api_key_modal_is_dismissible_and_does_not_block_keyless_corpus():
    html = (REPO_ROOT / "web" / "index.html").read_text(encoding="utf-8")
    js = (REPO_ROOT / "web" / "app.js").read_text(encoding="utf-8")
    assert 'id="key-close"' in html
    assert 'role="dialog"' in html and 'aria-modal="true"' in html
    assert '$("key-close").addEventListener("click", hideKeyModal)' in js
    assert 'e.key === "Escape"' in js
    assert 'else hideKeyModal();' in js
