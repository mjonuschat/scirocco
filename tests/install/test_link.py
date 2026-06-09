from __future__ import annotations


def _plugins(sandbox):
    return sandbox.klipper / "klippy" / "plugins" / "heater_chamber"


def _extras(sandbox):
    return sandbox.klipper / "klippy" / "extras" / "heater_chamber"


def test_links_into_extras_when_no_plugins_dir(sandbox) -> None:
    (sandbox.klipper / "klippy" / "extras").mkdir(parents=True)
    proc = sandbox.run("link_extension")
    assert proc.returncode == 0, proc.stderr
    link = _extras(sandbox)
    assert link.is_symlink()
    assert link.resolve() == (sandbox.repo / "heater_chamber").resolve()


def test_prefers_plugins_when_present(sandbox) -> None:
    (sandbox.klipper / "klippy" / "extras").mkdir(parents=True)
    sandbox.make_plugins_dir()
    proc = sandbox.run("link_extension")
    assert proc.returncode == 0, proc.stderr
    assert _plugins(sandbox).is_symlink()
    assert not _extras(sandbox).exists()


def test_replaces_stale_symlink(sandbox) -> None:
    extras = sandbox.klipper / "klippy" / "extras"
    extras.mkdir(parents=True)
    stale = extras / "heater_chamber"
    stale.symlink_to(sandbox.home / "old")
    proc = sandbox.run("link_extension")
    assert proc.returncode == 0, proc.stderr
    assert stale.resolve() == (sandbox.repo / "heater_chamber").resolve()


def test_clears_other_location(sandbox) -> None:
    extras = sandbox.klipper / "klippy" / "extras"
    extras.mkdir(parents=True)
    sandbox.make_plugins_dir()
    # stale symlink left in extras from a previous extras-based install
    (extras / "heater_chamber").symlink_to(sandbox.home / "old")
    proc = sandbox.run("link_extension")
    assert proc.returncode == 0, proc.stderr
    assert _plugins(sandbox).is_symlink()
    assert not _extras(sandbox).exists()  # other location cleared


def test_aborts_when_selected_is_real_dir_without_mutating(sandbox) -> None:
    extras = sandbox.klipper / "klippy" / "extras"
    extras.mkdir(parents=True)
    real = extras / "heater_chamber"
    real.mkdir()
    (real / "keep.txt").write_text("mine")
    proc = sandbox.run("link_extension")
    assert proc.returncode != 0
    assert "not a symlink" in proc.stderr
    assert (real / "keep.txt").exists()  # untouched


def test_aborts_when_other_is_real_dir_leaving_selected_link_uncreated(sandbox) -> None:
    extras = sandbox.klipper / "klippy" / "extras"
    extras.mkdir(parents=True)
    sandbox.make_plugins_dir()
    # selected = plugins (will be created), other = extras is a REAL dir
    real = extras / "heater_chamber"
    real.mkdir()
    (real / "keep.txt").write_text("mine")
    proc = sandbox.run("link_extension")
    assert proc.returncode != 0
    assert "not a symlink" in proc.stderr
    assert not _plugins(sandbox).exists()  # nothing half-applied
    assert (real / "keep.txt").exists()


def test_unlink_removes_both_safe_links_and_skips_real(sandbox) -> None:
    extras = sandbox.klipper / "klippy" / "extras"
    plugins = sandbox.klipper / "klippy" / "plugins"
    extras.mkdir(parents=True)
    plugins.mkdir(parents=True)
    (extras / "heater_chamber").symlink_to(sandbox.repo / "heater_chamber")
    real = plugins / "heater_chamber"
    real.mkdir()
    proc = sandbox.run("unlink_extension")
    assert proc.returncode == 0, proc.stderr
    assert not _extras(sandbox).exists()  # symlink removed
    assert real.exists()  # real dir left alone
    assert "[SKIP]" in proc.stdout
