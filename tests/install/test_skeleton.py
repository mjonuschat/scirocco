from __future__ import annotations


def test_script_is_sourceable_and_resolves_config(sandbox) -> None:
    proc = sandbox.run('echo "HCP=${HEATER_CHAMBER_PATH}"; echo "MC=${MOONRAKER_CONFIG}"')
    assert proc.returncode == 0, proc.stderr
    assert f"HCP={sandbox.repo}" in proc.stdout
    assert "MC=" in proc.stdout


def test_unknown_subcommand_fails(sandbox) -> None:
    proc = sandbox.run("main bogus")
    assert proc.returncode != 0
    assert "usage:" in proc.stderr
