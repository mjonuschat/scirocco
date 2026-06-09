from __future__ import annotations


def test_classify_absent(sandbox) -> None:
    proc = sandbox.run(f'classify_path "{sandbox.home}/nope"')
    assert proc.stdout.strip() == "absent"


def test_classify_real_dir(sandbox) -> None:
    target = sandbox.home / "realdir"
    target.mkdir()
    proc = sandbox.run(f'classify_path "{target}"')
    assert proc.stdout.strip() == "real"


def test_classify_symlink(sandbox) -> None:
    link = sandbox.home / "lnk"
    link.symlink_to(sandbox.repo)
    proc = sandbox.run(f'classify_path "{link}"')
    assert proc.stdout.strip() == "symlink"


def test_classify_dangling_symlink_is_symlink(sandbox) -> None:
    link = sandbox.home / "dangling"
    link.symlink_to(sandbox.home / "missing-target")
    proc = sandbox.run(f'classify_path "{link}"')
    assert proc.stdout.strip() == "symlink"


def test_remove_safe_link_removes_symlink_returns_0(sandbox) -> None:
    link = sandbox.home / "lnk"
    link.symlink_to(sandbox.repo)
    proc = sandbox.run_probe(f'remove_safe_link "{link}"; echo "rc=$?"')
    assert "rc=0" in proc.stdout
    assert not link.exists() and not link.is_symlink()
    assert sandbox.repo.exists()  # target untouched


def test_remove_safe_link_absent_returns_1(sandbox) -> None:
    proc = sandbox.run_probe(f'remove_safe_link "{sandbox.home}/nope"; echo "rc=$?"')
    assert "rc=1" in proc.stdout


def test_remove_safe_link_refuses_real_dir_returns_2(sandbox) -> None:
    target = sandbox.home / "realdir"
    target.mkdir()
    proc = sandbox.run_probe(f'remove_safe_link "{target}"; echo "rc=$?"')
    assert "rc=2" in proc.stdout
    assert target.exists()  # not removed
