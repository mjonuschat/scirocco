from __future__ import annotations

from conftest import print_json


def _run_state(sandbox, state):
    return sandbox.run_probe(
        'check_no_active_print; echo "rc=$?"',
        extra_env={"FAKE_PRINT_JSON": print_json(state)},
    )


def test_idle_allows_restart(sandbox) -> None:
    assert "rc=0" in _run_state(sandbox, "standby").stdout


def test_complete_allows_restart(sandbox) -> None:
    assert "rc=0" in _run_state(sandbox, "complete").stdout


def test_printing_blocks_restart(sandbox) -> None:
    assert "rc=1" in _run_state(sandbox, "printing").stdout


def test_paused_blocks_restart(sandbox) -> None:
    assert "rc=1" in _run_state(sandbox, "paused").stdout


def test_unreachable_blocks_restart(sandbox) -> None:
    proc = sandbox.run_probe(
        'check_no_active_print; echo "rc=$?"',
        extra_env={"FAKE_CURL_FAIL": "1"},
    )
    assert "rc=1" in proc.stdout


def test_unknown_state_blocks_restart(sandbox) -> None:
    assert "rc=1" in _run_state(sandbox, "weird").stdout
