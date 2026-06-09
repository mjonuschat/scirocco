from __future__ import annotations


def test_add_updater_appends_block(sandbox) -> None:
    cfg = sandbox.write_moonraker()
    proc = sandbox.run("add_updater", extra_env={"MOONRAKER_CONFIG": str(cfg)})
    assert proc.returncode == 0, proc.stderr
    text = cfg.read_text()
    assert "[update_manager heater_chamber]" in text
    assert "# >>> heater_chamber >>>" in text
    assert "# <<< heater_chamber <<<" in text
    assert "install_script" not in text


def test_add_updater_is_idempotent(sandbox) -> None:
    cfg = sandbox.write_moonraker()
    sandbox.run("add_updater", extra_env={"MOONRAKER_CONFIG": str(cfg)})
    sandbox.run("add_updater", extra_env={"MOONRAKER_CONFIG": str(cfg)})
    assert cfg.read_text().count("[update_manager heater_chamber]") == 1


def test_add_updater_missing_config_warns_not_fatal(sandbox, tmp_path) -> None:
    missing = tmp_path / "nope.conf"
    proc = sandbox.run("add_updater", extra_env={"MOONRAKER_CONFIG": str(missing)})
    assert proc.returncode == 0
    assert "WARN" in proc.stdout or "WARN" in proc.stderr


def test_remove_updater_strips_block_only(sandbox) -> None:
    cfg = sandbox.write_moonraker("[server]\nhost: 0.0.0.0\n")
    sandbox.run("add_updater", extra_env={"MOONRAKER_CONFIG": str(cfg)})
    proc = sandbox.run("remove_updater", extra_env={"MOONRAKER_CONFIG": str(cfg)})
    assert proc.returncode == 0, proc.stderr
    text = cfg.read_text()
    assert "heater_chamber" not in text
    assert "[server]" in text  # surrounding config preserved


def test_remove_updater_missing_config_is_noop(sandbox, tmp_path) -> None:
    missing = tmp_path / "nope.conf"
    proc = sandbox.run("remove_updater", extra_env={"MOONRAKER_CONFIG": str(missing)})
    assert proc.returncode == 0
