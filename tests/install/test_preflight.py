from __future__ import annotations

from pathlib import Path

from conftest import info_json

STUB_PY = Path(__file__).resolve().parent / "bin" / "fakepython"


def test_python_version_accepts_311(sandbox) -> None:
    proc = sandbox.run(
        f'check_python_version "{STUB_PY}"; echo "rc=$?"',
        extra_env={"FAKE_PY_MAJOR": "3", "FAKE_PY_MINOR": "11"},
    )
    assert "rc=0" in proc.stdout


def test_python_version_rejects_310(sandbox) -> None:
    proc = sandbox.run(
        f'check_python_version "{STUB_PY}"',
        extra_env={"FAKE_PY_MAJOR": "3", "FAKE_PY_MINOR": "10"},
    )
    assert proc.returncode != 0
    assert "3.11" in proc.stderr


def test_preflight_adopts_klipper_path_and_caches_app(sandbox) -> None:
    sandbox.make_kalico(dual_loop=True)
    js = info_json(app="Kalico", python_path=str(STUB_PY), klipper_path=str(sandbox.klipper))
    proc = sandbox.run(
        'preflight_checks; echo "APP=${KALICO_APP}"; echo "rc=$?"',
        extra_env={
            "FAKE_INFO_JSON": js,
            "FAKE_PY_MAJOR": "3",
            "FAKE_PY_MINOR": "13",
            "KLIPPER_PATH": "",
        },
    )
    assert "rc=0" in proc.stdout, proc.stderr
    assert "APP=Kalico" in proc.stdout


def test_preflight_fails_without_klipper_service(sandbox) -> None:
    sandbox.make_kalico(dual_loop=True)
    js = info_json(python_path=str(STUB_PY))
    proc = sandbox.run(
        "preflight_checks",
        extra_env={"FAKE_INFO_JSON": js, "FAKE_KLIPPER_SERVICE": "0"},
    )
    assert proc.returncode != 0
    assert "Klipper" in proc.stderr


def test_preflight_refuses_root(sandbox) -> None:
    proc = sandbox.run("preflight_checks", extra_env={"INSTALL_UID": "0"})
    assert proc.returncode != 0
    assert "root" in proc.stderr


def test_restart_skipped_when_printing(sandbox) -> None:
    from conftest import print_json

    proc = sandbox.run("restart_klipper", extra_env={"FAKE_PRINT_JSON": print_json("printing")})
    assert proc.returncode == 0
    assert "NOTICE" in proc.stdout


def test_restart_runs_when_idle(sandbox) -> None:
    from conftest import print_json

    proc = sandbox.run("restart_klipper", extra_env={"FAKE_PRINT_JSON": print_json("standby")})
    assert proc.returncode == 0
    assert "Restarting" in proc.stdout


def test_resolve_klipper_path_defaults_when_unset_and_offline(sandbox) -> None:
    proc = sandbox.run(
        'unset KLIPPER_PATH; resolve_klipper_path; echo "KP=${KLIPPER_PATH}"',
        extra_env={"FAKE_CURL_FAIL": "1"},
    )
    assert f"KP={sandbox.klipper}" in proc.stdout  # ${HOME}/klipper default


def test_resolve_klipper_path_adopts_moonraker_value(sandbox) -> None:
    proc = sandbox.run(
        'unset KLIPPER_PATH; resolve_klipper_path; echo "KP=${KLIPPER_PATH}"',
        extra_env={"FAKE_INFO_JSON": info_json(klipper_path="/opt/kalico")},
    )
    assert "KP=/opt/kalico" in proc.stdout
