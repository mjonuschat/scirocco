from __future__ import annotations

import klippy.extras.heater_chamber as heater_chamber
import pytest
from tests.fakes import FakeConfig, FakeFanModule, FakePrinter, FakeSensorGeneric
from tests.test_heater_chamber_init import base_values


@pytest.fixture(autouse=True)
def patch_kalico_dependencies(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(heater_chamber, "PrinterSensorGeneric", FakeSensorGeneric)
    monkeypatch.setattr(heater_chamber, "fan", FakeFanModule)


def test_ready_event_registers_fan_timer() -> None:
    printer = FakePrinter()
    config = FakeConfig(values=base_values(), printer=printer)
    chamber = heater_chamber.load_config(config)

    chamber._handle_ready()

    assert printer.reactor.registered_timers == [chamber._fan_callback]


def test_fan_turns_on_when_heater_has_target() -> None:
    printer = FakePrinter()
    config = FakeConfig(values=base_values() | {"fan_speed": "0.65"}, printer=printer)
    chamber = heater_chamber.load_config(config)
    chamber.heater.target = 45.0
    chamber.element_sensor.temperature = 25.0

    next_time = chamber._fan_callback(12.0)

    assert chamber.fan.speed_calls == [(12.0, 0.65)]
    assert next_time == 13.0


def test_fan_turns_on_when_element_temperature_is_above_threshold() -> None:
    printer = FakePrinter()
    config = FakeConfig(values=base_values() | {"fan_heater_temp": "50.0"}, printer=printer)
    chamber = heater_chamber.load_config(config)
    chamber.heater.target = 0.0
    chamber.element_sensor.temperature = 51.0

    chamber._fan_callback(20.0)

    assert chamber.fan.speed_calls == [(20.0, 1.0)]


def test_fan_turns_off_when_idle_and_element_is_below_threshold() -> None:
    printer = FakePrinter()
    config = FakeConfig(values=base_values() | {"fan_heater_temp": "50.0"}, printer=printer)
    chamber = heater_chamber.load_config(config)
    chamber.heater.target = 0.0
    chamber.element_sensor.temperature = 49.0

    chamber._fan_callback(30.0)

    assert chamber.fan.speed_calls == [(30.0, 0.0)]
