from __future__ import annotations

import klippy.extras.heater_chamber as heater_chamber
import pytest
from tests.fakes import FakeConfig, FakeFanModule, FakeGCmd, FakePrinter, FakeSensorGeneric
from tests.test_heater_chamber_init import base_values


@pytest.fixture(autouse=True)
def patch_kalico_dependencies(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(heater_chamber, "PrinterSensorGeneric", FakeSensorGeneric)
    monkeypatch.setattr(heater_chamber, "fan", FakeFanModule)


def test_default_instance_registers_m141_and_m191() -> None:
    printer = FakePrinter()
    config = FakeConfig(values=base_values(), printer=printer)

    chamber = heater_chamber.load_config(config)

    assert printer.gcode.commands == {
        "M141": chamber.cmd_M141,
        "M191": chamber.cmd_M191,
    }


def test_named_instance_does_not_register_marlin_gcodes() -> None:
    printer = FakePrinter()
    config = FakeConfig(name="heater_chamber rear", values=base_values(), printer=printer)

    heater_chamber.load_config_prefix(config)

    assert printer.gcode.commands == {}


def test_m141_without_s_parameter_does_nothing() -> None:
    printer = FakePrinter()
    config = FakeConfig(values=base_values(), printer=printer)
    chamber = heater_chamber.load_config(config)

    chamber.cmd_M141(FakeGCmd())

    assert printer.heaters.set_temperature_calls == []
    assert printer.gcode.scripts == []


def test_m141_sets_target_without_waiting() -> None:
    printer = FakePrinter()
    config = FakeConfig(values=base_values(), printer=printer)
    chamber = heater_chamber.load_config(config)

    chamber.cmd_M141(FakeGCmd({"S": "55"}))

    assert printer.heaters.set_temperature_calls == [(chamber.heater, 55.0, False)]
    assert printer.gcode.scripts == []


def test_m191_s_waits_only_when_current_temperature_is_below_target() -> None:
    printer = FakePrinter()
    config = FakeConfig(values=base_values(), printer=printer)
    chamber = heater_chamber.load_config(config)
    chamber.heater.temperature = 40.0

    chamber.cmd_M191(FakeGCmd({"S": "55"}))

    assert printer.heaters.set_temperature_calls == [(chamber.heater, 55.0, False)]
    assert printer.gcode.scripts == ["TEMPERATURE_WAIT SENSOR=heater_chamber MINIMUM=55"]


def test_m191_s_returns_immediately_when_current_temperature_is_above_target() -> None:
    printer = FakePrinter()
    config = FakeConfig(values=base_values(), printer=printer)
    chamber = heater_chamber.load_config(config)
    chamber.heater.temperature = 60.0

    chamber.cmd_M191(FakeGCmd({"S": "55"}))

    assert printer.heaters.set_temperature_calls == [(chamber.heater, 55.0, False)]
    assert printer.gcode.scripts == []


def test_m191_r_waits_for_heating_or_cooling_and_takes_precedence_over_s() -> None:
    printer = FakePrinter()
    config = FakeConfig(values=base_values(), printer=printer)
    chamber = heater_chamber.load_config(config)
    chamber.heater.temperature = 60.0

    chamber.cmd_M191(FakeGCmd({"S": "70", "R": "55"}))

    assert printer.heaters.set_temperature_calls == [(chamber.heater, 55.0, False)]
    assert printer.gcode.scripts == ["TEMPERATURE_WAIT SENSOR=heater_chamber MAXIMUM=55"]


def test_m191_without_s_or_r_does_nothing() -> None:
    printer = FakePrinter()
    config = FakeConfig(values=base_values(), printer=printer)
    chamber = heater_chamber.load_config(config)

    chamber.cmd_M191(FakeGCmd())

    assert printer.heaters.set_temperature_calls == []
    assert printer.gcode.scripts == []
