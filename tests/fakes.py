from __future__ import annotations

from collections.abc import Mapping, Sequence
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
