from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALL_SH = REPO_ROOT / "install.sh"
STUB_BIN = Path(__file__).resolve().parent / "bin"


@dataclass
class Sandbox:
    home: Path
    klipper: Path
    repo: Path
    env: dict[str, str] = field(default_factory=dict)

    def write_moonraker(self, text: str = "[server]\nhost: 0.0.0.0\n") -> Path:
        cfg_dir = self.home / "printer_data" / "config"
        cfg_dir.mkdir(parents=True, exist_ok=True)
        cfg = cfg_dir / "moonraker.conf"
        cfg.write_text(text)
        return cfg

    def make_kalico(self, *, dual_loop: bool = True, danger: bool = True) -> None:
        extras = self.klipper / "klippy" / "extras"
        extras.mkdir(parents=True, exist_ok=True)
        body = "algos = {'pid': 1}\n"
        if dual_loop:
            body += "register('dual_loop_pid')\n"
        (extras / "heaters.py").write_text(body)
        danger_file = extras / "danger_options.py"
        if danger:
            danger_file.write_text("# kalico\n")
        elif danger_file.exists():
            danger_file.unlink()  # simulate true mainline (no Kalico marker)

    def make_plugins_dir(self) -> None:
        (self.klipper / "klippy" / "plugins").mkdir(parents=True, exist_ok=True)

    def _exec(self, script: str, extra_env: dict[str, str] | None) -> subprocess.CompletedProcess:
        env = dict(os.environ)
        env["PATH"] = f"{STUB_BIN}:{env['PATH']}"
        env["HOME"] = str(self.home)
        env.update(self.env)
        if extra_env:
            env.update(extra_env)
        return subprocess.run(["bash", "-c", script], env=env, capture_output=True, text=True)

    def run(
        self, call: str, *, extra_env: dict[str, str] | None = None
    ) -> subprocess.CompletedProcess:
        # Real `set -e` (install.sh's default) so integration and abort paths match the
        # production entrypoint: an unchecked `ln -s`/`mv` failure aborts here too.
        script = f'source "{INSTALL_SH}"\nresolve_config\n{call}\n'
        return self._exec(script, extra_env)

    def run_probe(
        self, call: str, *, extra_env: dict[str, str] | None = None
    ) -> subprocess.CompletedProcess:
        # `set +e` ONLY for return-code probes (`func; echo "rc=$?"`) where a non-zero
        # return is the thing under test and must not abort before the echo. Never use
        # this for integration/entrypoint tests — those must keep real `set -e`.
        script = f'source "{INSTALL_SH}"\nset +e\nresolve_config\n{call}\n'
        return self._exec(script, extra_env)


@pytest.fixture
def sandbox(tmp_path: Path) -> Sandbox:
    home = tmp_path / "home"
    klipper = home / "klipper"
    repo = home / "heater_chamber"
    (repo / "heater_chamber").mkdir(parents=True)
    (repo / "heater_chamber" / "__init__.py").write_text("")
    (repo / "install.sh").write_text("")
    home.mkdir(exist_ok=True)
    klipper.mkdir(parents=True, exist_ok=True)
    env = {
        "KLIPPER_PATH": str(klipper),
        "HEATER_CHAMBER_PATH": str(repo),
        "MOONRAKER_HOST": "http://localhost:7125",
        "JSON_PY": "python3",
        # Default to a non-root uid so preflight's root-refusal does not fire under
        # rootful CI/containers. The root-refusal test overrides this to "0".
        "INSTALL_UID": "1000",
    }
    return Sandbox(home=home, klipper=klipper, repo=repo, env=env)


def info_json(app: str = "Kalico", python_path: str = "/x/py", klipper_path: str = "") -> str:
    result = {"app": app, "python_path": python_path}
    if klipper_path:
        result["klipper_path"] = klipper_path
    return json.dumps({"result": result})


def print_json(state: str) -> str:
    return json.dumps({"result": {"status": {"print_stats": {"state": state}}}})
