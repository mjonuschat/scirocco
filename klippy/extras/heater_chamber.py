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
