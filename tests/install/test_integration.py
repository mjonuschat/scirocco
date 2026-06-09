from __future__ import annotations

from pathlib import Path

from conftest import info_json, print_json

STUB_PY = Path(__file__).resolve().parent / "bin" / "fakepython"


def _env(sandbox):
    cfg = sandbox.write_moonraker()
    (sandbox.klipper / "klippy" / "extras").mkdir(parents=True, exist_ok=True)
    sandbox.make_kalico(dual_loop=True)
    return {
        "FAKE_INFO_JSON": info_json(
            app="Kalico", python_path=str(STUB_PY), klipper_path=str(sandbox.klipper)
        ),
        "FAKE_PRINT_JSON": print_json("standby"),
        "FAKE_PY_MAJOR": "3",
        "FAKE_PY_MINOR": "13",
        "MOONRAKER_CONFIG": str(cfg),
    }


def test_full_install_links_and_registers(sandbox) -> None:
    env = _env(sandbox)
    proc = sandbox.run("main install", extra_env=env)
    assert proc.returncode == 0, proc.stderr
    link = sandbox.klipper / "klippy" / "extras" / "heater_chamber"
    assert link.is_symlink()
    assert "[update_manager heater_chamber]" in Path(env["MOONRAKER_CONFIG"]).read_text()
    assert "[DONE] heater_chamber installed." in proc.stdout


def test_full_uninstall_reverses_install(sandbox) -> None:
    env = _env(sandbox)
    sandbox.run("main install", extra_env=env)
    proc = sandbox.run("main uninstall", extra_env=env)
    assert proc.returncode == 0, proc.stderr
    link = sandbox.klipper / "klippy" / "extras" / "heater_chamber"
    assert not link.exists()
    assert "heater_chamber" not in Path(env["MOONRAKER_CONFIG"]).read_text()


def test_install_aborts_on_mainline(sandbox) -> None:
    env = _env(sandbox)
    sandbox.make_kalico(dual_loop=False, danger=False)  # downgrade filesystem to mainline
    # Mainline also reports no Kalico app, so override the canned printer.info.
    env["FAKE_INFO_JSON"] = info_json(
        app="", python_path=str(STUB_PY), klipper_path=str(sandbox.klipper)
    )
    proc = sandbox.run("main install", extra_env=env)
    assert proc.returncode != 0
    assert "mainline Klipper" in proc.stderr
