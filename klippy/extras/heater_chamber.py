from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


class ConfigProxy:
    """Remap config keys while preserving ConfigWrapper behavior."""

    def __init__(
        self,
        config: Any,
        key_map: Mapping[str, str] | None = None,
        overrides: Mapping[str, Any] | None = None,
        name_override: str | None = None,
    ) -> None:
        self._config = config
        self._key_map = dict(key_map or {})
        self._overrides = dict(overrides or {})
        self._name_override = name_override
        self.error = config.error

    def _mapped_key(self, key: str) -> str:
        return self._key_map.get(key, key)

    def _has_override(self, key: str) -> bool:
        return key in self._overrides

    def _override(self, key: str) -> Any:
        return self._overrides[key]

    def _read(self, method_name: str, key: str, *args: Any, **kwargs: Any) -> Any:
        if self._has_override(key):
            return self._override(key)
        method = getattr(self._config, method_name)
        return method(self._mapped_key(key), *args, **kwargs)

    def _arg_value(
        self,
        args: tuple[Any, ...],
        kwargs: Mapping[str, Any],
        name: str,
        position: int,
        default: Any = None,
    ) -> Any:
        if name in kwargs:
            return kwargs[name]
        if len(args) > position:
            return args[position]
        return default

    def _validate_number(
        self,
        key: str,
        value: int | float,
        *,
        minval: int | float | None = None,
        maxval: int | float | None = None,
        above: int | float | None = None,
        below: int | float | None = None,
    ) -> None:
        if minval is not None and value < minval:
            raise self.error(f"Option '{key}' must have minimum of {minval}")
        if maxval is not None and value > maxval:
            raise self.error(f"Option '{key}' must have maximum of {maxval}")
        if above is not None and value <= above:
            raise self.error(f"Option '{key}' must be above {above}")
        if below is not None and value >= below:
            raise self.error(f"Option '{key}' must be below {below}")

    def _parse_override_lists(
        self,
        key: str,
        *,
        seps: Sequence[str],
        count: int | None,
        parser: Any,
    ) -> list[Any]:
        def parse(value: Any, pos: int) -> list[Any]:
            if isinstance(value, str):
                if len(value.strip()) == 0:
                    parts: list[Any] = []
                else:
                    parts = [part.strip() for part in value.split(seps[pos])]
            else:
                parts = list(value)

            if pos:
                return [parse(part, pos - 1) for part in parts if part]

            try:
                parsed = [parser(part) for part in parts]
            except Exception as exc:
                raise self.error(f"Unable to parse option '{key}'") from exc
            if count is not None and len(parsed) != count:
                raise self.error(f"Option '{key}' must have {count} elements")
            return parsed

        return parse(self._override(key), len(seps) - 1)

    def get_name(self) -> str:
        if self._name_override is not None:
            return self._name_override
        return self._config.get_name()

    def get(self, key: str, *args: Any, **kwargs: Any) -> Any:
        return self._read("get", key, *args, **kwargs)

    def getfloat(self, key: str, *args: Any, **kwargs: Any) -> float:
        if self._has_override(key):
            try:
                value = float(self._override(key))
            except Exception as exc:
                raise self.error(f"Unable to parse option '{key}'") from exc
            self._validate_number(
                key,
                value,
                minval=self._arg_value(args, kwargs, "minval", 1),
                maxval=self._arg_value(args, kwargs, "maxval", 2),
                above=self._arg_value(args, kwargs, "above", 3),
                below=self._arg_value(args, kwargs, "below", 4),
            )
            return value
        return self._read("getfloat", key, *args, **kwargs)

    def getint(self, key: str, *args: Any, **kwargs: Any) -> int:
        if self._has_override(key):
            try:
                value = int(self._override(key))
            except Exception as exc:
                raise self.error(f"Unable to parse option '{key}'") from exc
            self._validate_number(
                key,
                value,
                minval=self._arg_value(args, kwargs, "minval", 1),
                maxval=self._arg_value(args, kwargs, "maxval", 2),
            )
            return value
        return self._read("getint", key, *args, **kwargs)

    def getboolean(self, key: str, *args: Any, **kwargs: Any) -> bool:
        if self._has_override(key):
            value = self._override(key)
            if isinstance(value, bool):
                return value
            normalized = str(value).lower()
            if normalized in {"1", "true", "yes", "on"}:
                return True
            if normalized in {"0", "false", "no", "off"}:
                return False
            raise self.error(f"Unable to parse option '{key}'")
        return self._read("getboolean", key, *args, **kwargs)

    def getchoice(self, key: str, *args: Any, **kwargs: Any) -> Any:
        if self._has_override(key):
            choices = args[0] if args else kwargs["choices"]
            if isinstance(choices, list):
                choices = {choice: choice for choice in choices}
            if choices and isinstance(next(iter(choices)), int):
                choice = self.getint(
                    key, *args[1:], **{k: v for k, v in kwargs.items() if k != "choices"}
                )
            else:
                choice = self.get(key)
            if choice not in choices:
                raise self.error(f"Choice '{choice}' for option '{key}' is not a valid choice")
            return choices[choice]
        return self._read("getchoice", key, *args, **kwargs)

    def getlist(self, key: str, *args: Any, **kwargs: Any) -> list[Any]:
        if self._has_override(key):
            return self._parse_override_lists(
                key,
                seps=(self._arg_value(args, kwargs, "sep", 1, ","),),
                count=self._arg_value(args, kwargs, "count", 2),
                parser=str,
            )
        return self._read("getlist", key, *args, **kwargs)

    def getfloatlist(self, key: str, *args: Any, **kwargs: Any) -> list[float]:
        if self._has_override(key):
            return self._parse_override_lists(
                key,
                seps=(self._arg_value(args, kwargs, "sep", 1, ","),),
                count=self._arg_value(args, kwargs, "count", 2),
                parser=float,
            )
        return self._read("getfloatlist", key, *args, **kwargs)

    def getintlist(self, key: str, *args: Any, **kwargs: Any) -> list[int]:
        if self._has_override(key):
            return self._parse_override_lists(
                key,
                seps=(self._arg_value(args, kwargs, "sep", 1, ","),),
                count=self._arg_value(args, kwargs, "count", 2),
                parser=int,
            )
        return self._read("getintlist", key, *args, **kwargs)

    def getlists(self, key: str, *args: Any, **kwargs: Any) -> list[list[Any]]:
        if self._has_override(key):
            return self._parse_override_lists(
                key,
                seps=self._arg_value(args, kwargs, "seps", 1, (",",)),
                count=self._arg_value(args, kwargs, "count", 2),
                parser=self._arg_value(args, kwargs, "parser", 3, str),
            )
        return self._read("getlists", key, *args, **kwargs)

    def get_printer(self) -> Any:
        return self._config.get_printer()

    def getsection(self, section: str) -> Any:
        return self._config.getsection(section)

    def has_section(self, section: str) -> bool:
        return self._config.has_section(section)

    def get_prefix_sections(self, prefix: str) -> Sequence[Any]:
        return self._config.get_prefix_sections(prefix)

    def get_prefix_options(self, prefix: str) -> Sequence[Any]:
        return self._config.get_prefix_options(prefix)

    def deprecate(self, option: str, value: Any = None) -> None:
        self._config.deprecate(self._mapped_key(option), value)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._config, name)


try:
    from . import fan
except ImportError:
    fan = None  # type: ignore[assignment]

try:
    from .temperature_sensor import PrinterSensorGeneric
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
