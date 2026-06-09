from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any

_MISSING = object()


class FakeConfigError(Exception):
    """Config error raised by FakeConfig."""


class FakeConfig:
    def __init__(
        self,
        name: str = "heater_chamber",
        values: Mapping[str, Any] | None = None,
        printer: Any = None,
    ) -> None:
        self._name = name
        self.values = dict(values or {})
        self.printer = printer
        self.error = FakeConfigError
        self.accessed: list[str] = []
        self.deprecated: list[Any] = []

    def get_name(self) -> str:
        return self._name

    def get_printer(self) -> Any:
        return self.printer

    def _read(self, key: str, default: Any = _MISSING) -> Any:
        self.accessed.append(key)
        if key in self.values:
            return self.values[key]
        if default is not _MISSING:
            return default
        raise self.error(f"Missing option {key}")

    def get(self, key: str, default: Any = _MISSING) -> Any:
        return self._read(key, default)

    def getfloat(self, key: str, default: Any = _MISSING, **_: Any) -> float:
        return float(self._read(key, default))

    def getint(self, key: str, default: Any = _MISSING, **_: Any) -> int:
        return int(self._read(key, default))

    def getboolean(self, key: str, default: Any = _MISSING) -> bool:
        value = self._read(key, default)
        if isinstance(value, bool):
            return value
        return str(value).lower() in {"1", "true", "yes", "on"}

    def getchoice(self, key: str, choices: Mapping[str, Any], default: Any = _MISSING) -> Any:
        value = self._read(key, default)
        return choices[value]

    def getlist(self, key: str, default: Any = _MISSING, **_: Any) -> list[str]:
        value = self._read(key, default)
        if isinstance(value, str):
            return [part.strip() for part in value.split(",")]
        return list(value)

    def getfloatlist(self, key: str, default: Any = _MISSING, **_: Any) -> list[float]:
        return [float(item) for item in self.getlist(key, default)]

    def getintlist(self, key: str, default: Any = _MISSING, **_: Any) -> list[int]:
        return [int(item) for item in self.getlist(key, default)]

    def getlists(self, key: str, default: Any = _MISSING, **_: Any) -> list[list[str]]:
        value = self._read(key, default)
        if isinstance(value, str):
            return [[part.strip() for part in row.split(",")] for row in value.splitlines()]
        return [list(row) for row in value]

    def getsection(self, section: str) -> str:
        return f"section:{section}"

    def has_section(self, section: str) -> bool:
        return section in self.values.get("_sections", set())

    def get_prefix_sections(self, prefix: str) -> Sequence[str]:
        return tuple(self.values.get(f"_prefix_sections:{prefix}", ()))

    def get_prefix_options(self, prefix: str) -> Sequence[str]:
        return tuple(self.values.get(f"_prefix_options:{prefix}", ()))

    def deprecate(self, option: str, value: Any = None) -> None:
        if value is None:
            self.deprecated.append(option)
            return
        self.deprecated.append((option, value))


class FakeSensorGeneric:
    def __init__(self, config: Any) -> None:
        self.config = config
        self.temperature = 25.0

    def get_temp(self, _eventtime: float) -> tuple[float, float]:
        return self.temperature, 0.0


class FakeHeater:
    def __init__(self, config: Any) -> None:
        self.config = config
        self.temperature = 25.0
        self.target = 0.0

    def get_temp(self, _eventtime: float) -> tuple[float, float]:
        return self.temperature, self.target


class FakeHeaters:
    def __init__(self) -> None:
        self.setup_calls: list[tuple[Any, str | None]] = []
        self.set_temperature_calls: list[tuple[FakeHeater, float, bool]] = []
        self.created_heaters: list[FakeHeater] = []

    def setup_heater(self, config: Any, gcode_id: str | None = None) -> FakeHeater:
        heater = FakeHeater(config)
        self.setup_calls.append((config, gcode_id))
        self.created_heaters.append(heater)
        return heater

    def set_temperature(self, heater: FakeHeater, target: float, wait: bool = False) -> None:
        heater.target = target
        self.set_temperature_calls.append((heater, target, wait))


class FakeFan:
    def __init__(self, config: Any, default_shutdown_speed: float = 0.0) -> None:
        self.config = config
        self.default_shutdown_speed = default_shutdown_speed
        self.speed_calls: list[tuple[float, float]] = []

    def set_speed(self, eventtime: float, speed: float) -> None:
        self.speed_calls.append((eventtime, speed))


class FakeFanModule:
    Fan = FakeFan


class FakeGCode:
    def __init__(self) -> None:
        self.commands: dict[str, Callable[[Any], None]] = {}
        self.scripts: list[str] = []

    def register_command(self, name: str, callback: Callable[[Any], None]) -> None:
        self.commands[name] = callback

    def run_script_from_command(self, command: str) -> None:
        self.scripts.append(command)


class FakeReactor:
    def __init__(self) -> None:
        self.registered_timers: list[Callable[[float], float]] = []
        self._time = 100.0

    def monotonic(self) -> float:
        return self._time

    def register_timer(
        self, callback: Callable[[float], float], _waketime: float
    ) -> Callable[[float], float]:
        self.registered_timers.append(callback)
        return callback


class FakePrinter:
    def __init__(self) -> None:
        self.objects: dict[str, Any] = {}
        self.heaters = FakeHeaters()
        self.gcode = FakeGCode()
        self.reactor = FakeReactor()
        self.event_handlers: dict[str, list[Callable[[], None]]] = {}

    def add_object(self, name: str, obj: Any) -> None:
        self.objects[name] = obj

    def load_object(self, _config: Any, name: str) -> Any:
        if name == "heaters":
            return self.heaters
        raise KeyError(name)

    def lookup_object(self, name: str) -> Any:
        if name == "gcode":
            return self.gcode
        if name in self.objects:
            return self.objects[name]
        raise KeyError(name)

    def get_reactor(self) -> FakeReactor:
        return self.reactor

    def register_event_handler(self, event: str, callback: Callable[[], None]) -> None:
        self.event_handlers.setdefault(event, []).append(callback)


class FakeGCmd:
    def __init__(self, params: Mapping[str, Any] | None = None) -> None:
        self.params = dict(params or {})

    def get_float(self, name: str, default: Any = None, **_: Any) -> float | None:
        if name not in self.params:
            return default
        return float(self.params[name])
