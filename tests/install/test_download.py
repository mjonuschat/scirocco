from __future__ import annotations


def test_existing_checkout_skips_clone(sandbox) -> None:
    # sandbox.repo already has heater_chamber/__init__.py
    proc = sandbox.run('check_download; echo "rc=$?"')
    assert "rc=0" in proc.stdout
    assert "Using existing checkout" in proc.stdout


def test_absent_target_clones(sandbox, tmp_path) -> None:
    dest = tmp_path / "fresh"
    proc = sandbox.run("check_download", extra_env={"HEATER_CHAMBER_PATH": str(dest)})
    assert proc.returncode == 0, proc.stderr
    assert (dest / "heater_chamber" / "__init__.py").exists()


def test_empty_target_clones(sandbox, tmp_path) -> None:
    dest = tmp_path / "empty"
    dest.mkdir()
    proc = sandbox.run("check_download", extra_env={"HEATER_CHAMBER_PATH": str(dest)})
    assert proc.returncode == 0, proc.stderr
    assert (dest / "heater_chamber" / "__init__.py").exists()


def test_nonempty_invalid_target_aborts(sandbox, tmp_path) -> None:
    dest = tmp_path / "junk"
    dest.mkdir()
    (dest / "unrelated.txt").write_text("x")
    proc = sandbox.run("check_download", extra_env={"HEATER_CHAMBER_PATH": str(dest)})
    assert proc.returncode != 0
    assert "not a heater_chamber checkout" in proc.stderr


def test_clone_failure_aborts(sandbox, tmp_path) -> None:
    dest = tmp_path / "fresh"
    proc = sandbox.run(
        "check_download",
        extra_env={"HEATER_CHAMBER_PATH": str(dest), "FAKE_GIT_FAIL": "1"},
    )
    assert proc.returncode != 0
    assert "clone" in proc.stderr.lower()
