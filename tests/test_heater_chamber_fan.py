from __future__ import annotations

import heater_chamber.controller as heater_chamber
import pytest
from tests.fakes import FakeConfig, FakeFanModule, FakeGCmd, FakePrinter, FakeSensorGeneric
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
    assert printer.reactor.registered_waketimes == [100.1]


def test_fan_turns_on_when_heater_has_target() -> None:
    printer = FakePrinter()
    config = FakeConfig(values=base_values() | {"fan_speed": "0.65"}, printer=printer)
    chamber = heater_chamber.load_config(config)
    chamber.heater.target = 45.0
    chamber.element_sensor.temperature = 25.0

    next_time = chamber._fan_callback(12.0)

    assert chamber.fan.speed_calls == [(0.65, None)]
    assert next_time == 13.0


def test_fan_turns_on_when_element_temperature_is_above_threshold() -> None:
    printer = FakePrinter()
    config = FakeConfig(values=base_values() | {"fan_heater_temp": "50.0"}, printer=printer)
    chamber = heater_chamber.load_config(config)
    chamber.heater.target = 0.0
    chamber.element_sensor.temperature = 51.0

    chamber._fan_callback(20.0)

    assert chamber.fan.speed_calls == [(1.0, None)]


def test_fan_turns_off_after_heater_becomes_idle_and_element_is_below_threshold() -> None:
    printer = FakePrinter()
    config = FakeConfig(values=base_values() | {"fan_heater_temp": "50.0"}, printer=printer)
    chamber = heater_chamber.load_config(config)
    chamber.heater.target = 55.0
    chamber._fan_callback(29.0)

    chamber.heater.target = 0.0
    chamber.element_sensor.temperature = 49.0

    chamber._fan_callback(30.0)

    assert chamber.fan.speed_calls == [(1.0, None), (0.0, None)]


def test_fan_does_not_requeue_unchanged_speed() -> None:
    printer = FakePrinter()
    config = FakeConfig(values=base_values() | {"fan_speed": "0.65"}, printer=printer)
    chamber = heater_chamber.load_config(config)
    chamber.heater.target = 45.0

    chamber._fan_callback(12.0)
    chamber._fan_callback(13.0)

    assert chamber.fan.speed_calls == [(0.65, None)]


def test_fan_speed_control_is_not_registered_by_default() -> None:
    printer = FakePrinter()
    config = FakeConfig(values=base_values(), printer=printer)

    heater_chamber.load_config(config)

    assert ("SET_FAN_SPEED", "FAN", "heater_chamber") not in printer.gcode.mux_commands


def test_fan_speed_control_registers_opted_in_default_instance() -> None:
    printer = FakePrinter()
    config = FakeConfig(values=base_values() | {"fan_speed_control": "true"}, printer=printer)

    chamber = heater_chamber.load_config(config)

    assert printer.gcode.mux_commands[("SET_FAN_SPEED", "FAN", "heater_chamber")] == (
        chamber.cmd_SET_FAN_SPEED
    )


def test_fan_speed_control_registers_opted_in_named_instance() -> None:
    printer = FakePrinter()
    config = FakeConfig(
        name="heater_chamber rear",
        values=base_values() | {"fan_speed_control": "true"},
        printer=printer,
    )

    chamber = heater_chamber.load_config_prefix(config)

    assert printer.gcode.mux_commands[("SET_FAN_SPEED", "FAN", "rear")] == (
        chamber.cmd_SET_FAN_SPEED
    )


def test_set_fan_speed_updates_operating_speed_without_forcing_idle_fan() -> None:
    printer = FakePrinter()
    config = FakeConfig(values=base_values() | {"fan_speed_control": "true"}, printer=printer)
    chamber = heater_chamber.load_config(config)

    chamber.cmd_SET_FAN_SPEED(FakeGCmd({"SPEED": "0.45"}))

    assert chamber.fan_speed == 0.45
    assert chamber.fan.speed_calls == []


def test_set_fan_speed_applies_immediately_when_heater_is_active() -> None:
    printer = FakePrinter()
    config = FakeConfig(values=base_values() | {"fan_speed_control": "true"}, printer=printer)
    chamber = heater_chamber.load_config(config)
    chamber.heater.target = 45.0

    chamber.cmd_SET_FAN_SPEED(FakeGCmd({"SPEED": "0.45"}))

    assert chamber.fan_speed == 0.45
    assert chamber.fan.speed_calls == [(0.45, "gcode")]


def test_set_fan_speed_zero_warns_when_heater_is_active() -> None:
    printer = FakePrinter()
    config = FakeConfig(values=base_values() | {"fan_speed_control": "true"}, printer=printer)
    chamber = heater_chamber.load_config(config)
    chamber.heater.target = 45.0
    gcmd = FakeGCmd({"SPEED": "0"})

    chamber.cmd_SET_FAN_SPEED(gcmd)

    assert chamber.fan_speed == 0.0
    assert chamber.fan.speed_calls == [(0.0, "gcode")]
    assert gcmd.responses == [
        "Warning: heater_chamber fan speed set to 0 while chamber fan should be active"
    ]


def test_set_fan_speed_zero_warns_when_element_is_above_enable_temperature() -> None:
    printer = FakePrinter()
    config = FakeConfig(
        values=base_values() | {"fan_speed_control": "true", "fan_heater_temp": "50.0"},
        printer=printer,
    )
    chamber = heater_chamber.load_config(config)
    chamber.element_sensor.temperature = 51.0
    gcmd = FakeGCmd({"SPEED": "0"})

    chamber.cmd_SET_FAN_SPEED(gcmd)

    assert chamber.fan_speed == 0.0
    assert chamber.fan.speed_calls == [(0.0, "gcode")]
    assert gcmd.responses == [
        "Warning: heater_chamber fan speed set to 0 while chamber fan should be active"
    ]
