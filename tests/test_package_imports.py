from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path
from typing import Any


def _package_module(name: str, path: list[str] | None = None) -> types.ModuleType:
    module = types.ModuleType(name)
    module.__path__ = path or []  # type: ignore[attr-defined]
    return module


def test_controller_uses_kalico_extras_when_loaded_as_plugin(monkeypatch: Any) -> None:
    package_dir = Path(__file__).resolve().parents[1] / "heater_chamber"
    fake_fan = types.ModuleType("klippy.extras.fan")
    fake_temperature_sensor = types.ModuleType("klippy.extras.temperature_sensor")

    class FakePrinterSensorGeneric:
        pass

    fake_temperature_sensor.PrinterSensorGeneric = FakePrinterSensorGeneric

    fake_extras = _package_module("klippy.extras")
    fake_extras.fan = fake_fan  # type: ignore[attr-defined]

    modules = {
        "klippy": _package_module("klippy"),
        "klippy.extras": fake_extras,
        "klippy.extras.fan": fake_fan,
        "klippy.extras.temperature_sensor": fake_temperature_sensor,
        "klippy.plugins": _package_module("klippy.plugins"),
        "klippy.plugins.heater_chamber": _package_module(
            "klippy.plugins.heater_chamber",
            [str(package_dir)],
        ),
    }
    for name, module in modules.items():
        monkeypatch.setitem(sys.modules, name, module)

    spec = importlib.util.spec_from_file_location(
        "klippy.plugins.heater_chamber.controller",
        package_dir / "controller.py",
    )
    assert spec is not None
    assert spec.loader is not None

    controller = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, controller)
    spec.loader.exec_module(controller)

    assert controller.fan is fake_fan
    assert controller.PrinterSensorGeneric is FakePrinterSensorGeneric
