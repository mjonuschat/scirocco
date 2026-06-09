from __future__ import annotations

from typing import Any

from .config_proxy import ConfigProxy

try:
    from .. import fan
except ImportError:
    fan = None  # type: ignore[assignment]

try:
    from ..temperature_sensor import PrinterSensorGeneric
except ImportError:
    PrinterSensorGeneric = None  # type: ignore[assignment]


PIN_MIN_TIME = 0.100
FAN_UPDATE_TIME = 1.0
DEFAULT_FAN_SPEED = 1.0
DEFAULT_FAN_HEATER_TEMP = 50.0
DEFAULT_FAN_SHUTDOWN_SPEED = 1.0

ELEMENT_SENSOR_KEY_MAP = {
    "sensor_type": "heater_sensor_type",
    "sensor_pin": "heater_sensor_pin",
    "min_temp": "heater_min_temp",
    "max_temp": "heater_max_temp",
}

HEATER_KEY_MAP = {
    "sensor_type": "chamber_sensor_type",
    "sensor_pin": "chamber_sensor_pin",
    "min_temp": "chamber_min_temp",
    "max_temp": "chamber_max_temp",
    "inner_max_temp": "heater_target_temp",
}

FAN_KEY_MAP = {
    "pin": "fan_pin",
    "shutdown_speed": "fan_shutdown_speed",
    "kick_start_time": "fan_kick_start_time",
    "min_power": "fan_min_power",
    "off_below": "fan_off_below",
    "max_power": "fan_max_power",
    "cycle_time": "fan_cycle_time",
    "hardware_pwm": "fan_hardware_pwm",
    "enable_pin": "fan_enable_pin",
    "initial_speed": "fan_initial_speed",
    "tachometer_pin": "fan_tachometer_pin",
    "tachometer_ppr": "fan_tachometer_ppr",
    "tachometer_poll_interval": "fan_tachometer_poll_interval",
}


def _instance_name(config_name: str) -> str:
    parts = config_name.split(maxsplit=1)
    if len(parts) == 1:
        return "heater_chamber"
    return parts[1]


def _require_dependency(config: Any, dependency: Any, name: str) -> Any:
    if dependency is None:
        raise config.error(f"heater_chamber requires Kalico dependency {name}")
    return dependency


def _temperature_from_result(result: Any) -> float:
    if isinstance(result, tuple):
        return float(result[0])
    return float(result)


def _target_from_result(result: Any) -> float:
    if isinstance(result, tuple) and len(result) > 1:
        return float(result[1])
    return 0.0


def _format_temperature(value: float) -> str:
    return f"{value:g}"


class PrinterHeaterChamber:
    def __init__(self, config: Any) -> None:
        self.config = config
        self.printer = config.get_printer()
        self.config_name = config.get_name()
        self.name = _instance_name(self.config_name)
        self.is_default = self.config_name == "heater_chamber"

        control = config.get("control")
        if control != "dual_loop_pid":
            raise config.error("heater_chamber requires control: dual_loop_pid")

        sensor_cls = _require_dependency(config, PrinterSensorGeneric, "PrinterSensorGeneric")
        fan_module = _require_dependency(config, fan, "fan")

        self.pheaters = self.printer.load_object(config, "heaters")
        self.element_sensor_name = f"{self.name}_element"
        self.element_sensor = self._create_element_sensor(sensor_cls)
        self.heater = self._create_heater()
        self.fan = self._create_fan(fan_module)
        self.fan_speed = config.getfloat("fan_speed", DEFAULT_FAN_SPEED, minval=0.0, maxval=1.0)
        self.fan_heater_temp = config.getfloat("fan_heater_temp", DEFAULT_FAN_HEATER_TEMP)
        self.last_fan_speed = 0.0
        self._fan_timer = None

        self.printer.register_event_handler("klippy:ready", self._handle_ready)
        self.gcode = self.printer.lookup_object("gcode")
        if self.is_default:
            self.gcode.register_command("M141", self.cmd_M141)
            self.gcode.register_command("M191", self.cmd_M191)

    def _create_element_sensor(self, sensor_cls: Any) -> Any:
        sensor_object_name = f"temperature_sensor {self.element_sensor_name}"
        element_proxy = ConfigProxy(
            self.config,
            key_map=ELEMENT_SENSOR_KEY_MAP,
            name_override=sensor_object_name,
        )
        element_sensor = sensor_cls(element_proxy)
        self.printer.add_object(sensor_object_name, element_sensor)
        return element_sensor

    def _create_heater(self) -> Any:
        heater_proxy = ConfigProxy(
            self.config,
            key_map=HEATER_KEY_MAP,
            overrides={"inner_sensor_name": self.element_sensor_name},
            name_override=self.config_name,
        )
        gcode_id = "C" if self.is_default else None
        return self.pheaters.setup_heater(heater_proxy, gcode_id)

    def _create_fan(self, fan_module: Any) -> Any:
        fan_proxy = ConfigProxy(self.config, key_map=FAN_KEY_MAP, name_override=self.config_name)
        return fan_module.Fan(fan_proxy, default_shutdown_speed=DEFAULT_FAN_SHUTDOWN_SPEED)

    def _handle_ready(self) -> None:
        reactor = self.printer.get_reactor()
        self._fan_timer = reactor.register_timer(
            self._fan_callback, reactor.monotonic() + PIN_MIN_TIME
        )

    def _fan_callback(self, eventtime: float) -> float:
        element_temp = _temperature_from_result(self.element_sensor.get_temp(eventtime))
        target = _target_from_result(self.heater.get_temp(eventtime))
        fan_speed = self.fan_speed if target > 0.0 or element_temp >= self.fan_heater_temp else 0.0
        if fan_speed != self.last_fan_speed:
            self.last_fan_speed = fan_speed
            self.fan.set_speed(fan_speed)
        return eventtime + FAN_UPDATE_TIME

    def cmd_M141(self, gcmd: Any) -> None:
        target = gcmd.get_float("S", None)
        if target is None:
            return
        self._set_temperature(target)

    def cmd_M191(self, gcmd: Any) -> None:
        target = gcmd.get_float("R", None)
        wait_for_cooling = target is not None
        if target is None:
            target = gcmd.get_float("S", None)
        if target is None:
            return

        self._set_temperature(target)
        current = self._current_chamber_temperature()
        if current < target:
            self._temperature_wait(minimum=target)
        elif wait_for_cooling and current > target:
            self._temperature_wait(maximum=target)

    def _set_temperature(self, target: float) -> None:
        self.pheaters.set_temperature(self.heater, target, wait=False)

    def _current_chamber_temperature(self) -> float:
        reactor = self.printer.get_reactor()
        return _temperature_from_result(self.heater.get_temp(reactor.monotonic()))

    def _temperature_wait(
        self,
        minimum: float | None = None,
        maximum: float | None = None,
    ) -> None:
        if minimum is not None:
            self.gcode.run_script_from_command(
                f"TEMPERATURE_WAIT SENSOR={self.name} MINIMUM={_format_temperature(minimum)}"
            )
            return
        if maximum is not None:
            self.gcode.run_script_from_command(
                f"TEMPERATURE_WAIT SENSOR={self.name} MAXIMUM={_format_temperature(maximum)}"
            )


def load_config(config: Any) -> PrinterHeaterChamber:
    return PrinterHeaterChamber(config)


def load_config_prefix(config: Any) -> PrinterHeaterChamber:
    return PrinterHeaterChamber(config)
