from pathlib import Path

from plutus_wire_install import REPO_ROOT, SOURCE_DIR, TARGET_DIR


def test_one_command_installer_uses_repo_opencli_adapters():
    assert SOURCE_DIR == REPO_ROOT / "opencli-clis" / "plutus-wire"
    assert (SOURCE_DIR / "timeline.js").exists()
    assert (SOURCE_DIR / "health.js").exists()


def test_one_command_installer_targets_opencli_cli_dir():
    assert Path(TARGET_DIR).parts[-3:] == (".opencli", "clis", "plutus-wire")
