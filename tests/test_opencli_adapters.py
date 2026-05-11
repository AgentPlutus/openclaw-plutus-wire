from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
ADAPTER_DIR = REPO_ROOT / "opencli-clis" / "plutus-wire"


def test_plutus_wire_adapters_use_site_name():
    adapter_files = [
        path
        for path in ADAPTER_DIR.glob("*.js")
        if path.name != "README.md"
    ]
    assert adapter_files
    for path in adapter_files:
        text = path.read_text(encoding="utf-8")
        assert "site: 'plutus-wire'" in text
        assert "site: 'xradar'" not in text


def test_shared_imports_are_site_local():
    for path in ADAPTER_DIR.glob("*.js"):
        text = path.read_text(encoding="utf-8")
        assert "../_shared" not in text
        if path.name != "home-tabs.js":
            assert "./_shared/" in text
