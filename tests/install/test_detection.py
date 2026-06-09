from __future__ import annotations

from conftest import info_json


def test_json_get_reads_nested_field(sandbox) -> None:
    js = info_json(app="Kalico")
    proc = sandbox.run(f"printf '%s' '{js}' | json_get result app")
    assert proc.stdout.strip() == "Kalico"


def test_json_get_missing_key_is_empty(sandbox) -> None:
    proc = sandbox.run("printf '%s' '{}' | json_get result app")
    assert proc.stdout.strip() == ""


def test_require_kalico_passes_when_dual_loop_present(sandbox) -> None:
    sandbox.make_kalico(dual_loop=True, danger=True)
    proc = sandbox.run('require_kalico; echo "rc=$?"')
    assert "rc=0" in proc.stdout


def test_require_kalico_fails_on_mainline_with_clear_message(sandbox) -> None:
    sandbox.make_kalico(dual_loop=False, danger=False)
    proc = sandbox.run("require_kalico")
    assert proc.returncode != 0
    assert "looks like mainline Klipper" in proc.stderr


def test_require_kalico_fails_on_old_kalico_with_update_message(sandbox) -> None:
    sandbox.make_kalico(dual_loop=False, danger=True)
    proc = sandbox.run("require_kalico")
    assert proc.returncode != 0
    assert "too old" in proc.stderr


def test_require_kalico_uses_app_field_for_messaging(sandbox) -> None:
    # No danger_options.py, but Moonraker reported app=Kalico -> "too old" branch.
    sandbox.make_kalico(dual_loop=False, danger=False)
    proc = sandbox.run("KALICO_APP=Kalico require_kalico")
    assert proc.returncode != 0
    assert "too old" in proc.stderr
