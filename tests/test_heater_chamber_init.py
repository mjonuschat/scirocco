from __future__ import annotations

import klippy.extras.heater_chamber as heater_chamber
import pytest
from tests.fakes import FakeConfig, FakeConfigError, FakeFanModule, FakePrinter, FakeSensorGeneric


def base_values() -> dict[str, object]:
    return {
        "heater_pin": "PD12",
        "heater_sensor_type": "NTC 100K beta 3950",
        "heater_sensor_pin": "PF4",
        "heater_min_temp": "0",
        "heater_max_temp": "150",
        "chamber_sensor_type": "NTC 100K beta 3950",
        "chamber_sensor_pin": "PF5",
        "chamber_min_temp": "0",
        "chamber_max_temp": "80",
        "control": "dual_loop_pid",
        "pid_Kp": "10.0",
        "pid_Ki": "0.1",
        "pid_Kd": "30.0",
        "inner_pid_Kp": "20.0",
        "inner_pid_Ki": "1.5",
        "inner_pid_Kd": "80.0",
        "heater_target_temp": "120.0",
        "fan_pin": "PD13",
    }


@pytest.fixture(autouse=True)
def patch_kalico_dependencies(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(heater_chamber, "PrinterSensorGeneric", FakeSensorGeneric)
    monkeypatch.setattr(heater_chamber, "fan", FakeFanModule)


def test_default_instance_creates_generated_sensor_heater_and_fan() -> None:
    printer = FakePrinter()
    config = FakeConfig(values=base_values(), printer=printer)

    chamber = heater_chamber.load_config(config)

    assert chamber.name == "heater_chamber"
    assert "temperature_sensor heater_chamber_element" in printer.objects
    assert printer.objects["temperature_sensor heater_chamber_element"] is chamber.element_sensor
    assert chamber.element_sensor.config.get_name() == "temperature_sensor heater_chamber_element"
    assert chamber.element_sensor.config.get("sensor_type") == "NTC 100K beta 3950"
    assert chamber.element_sensor.config.get("sensor_pin") == "PF4"

    heater_config, gcode_id = printer.heaters.setup_calls[0]
    assert gcode_id == "C"
    assert heater_config.get_name() == "heater_chamber"
    assert heater_config.get("sensor_type") == "NTC 100K beta 3950"
    assert heater_config.get("sensor_pin") == "PF5"
    assert heater_config.get("inner_sensor_name") == "heater_chamber_element"
    assert heater_config.getfloat("inner_max_temp") == 120.0

    assert chamber.fan.config.get("pin") == "PD13"
    assert chamber.fan.default_shutdown_speed == 1.0
    assert chamber.fan_speed == 1.0
    assert chamber.fan_heater_temp == 50.0
    assert printer.event_handlers["klippy:ready"] == [chamber._handle_ready]


def test_named_instance_uses_suffix_name_and_no_default_gcode_id() -> None:
    printer = FakePrinter()
    config = FakeConfig(name="heater_chamber rear", values=base_values(), printer=printer)

    chamber = heater_chamber.load_config_prefix(config)

    assert chamber.name == "rear"
    assert "temperature_sensor rear_element" in printer.objects
    heater_config, gcode_id = printer.heaters.setup_calls[0]
    assert gcode_id is None
    assert heater_config.get_name() == "heater_chamber rear"
    assert heater_config.get("inner_sensor_name") == "rear_element"


def test_control_must_be_dual_loop_pid() -> None:
    printer = FakePrinter()
    values = base_values()
    values["control"] = "pid"
    config = FakeConfig(values=values, printer=printer)

    with pytest.raises(FakeConfigError, match="control: dual_loop_pid"):
        heater_chamber.load_config(config)


def test_fan_proxy_maps_prefixed_fan_options() -> None:
    printer = FakePrinter()
    config = FakeConfig(
        values=base_values()
        | {
            "fan_min_power": "0.2",
            "fan_max_power": "0.9",
            "fan_hardware_pwm": "true",
            "fan_enable_pin": "PD14",
            "fan_initial_speed": "0.4",
            "fan_tachometer_pin": "PD15",
        },
        printer=printer,
    )

    chamber = heater_chamber.load_config(config)

    assert chamber.fan.config.getfloat("min_power") == 0.2
    assert chamber.fan.config.getfloat("max_power") == 0.9
    assert chamber.fan.config.getboolean("hardware_pwm") is True
    assert chamber.fan.config.get("enable_pin") == "PD14"
    assert chamber.fan.config.getfloat("initial_speed") == 0.4
    assert chamber.fan.config.get("tachometer_pin") == "PD15"
