from __future__ import annotations

import pytest
from heater_chamber.config_proxy import ConfigProxy
from tests.fakes import FakeConfig, FakeConfigError


def test_proxy_maps_getters_to_real_config_keys() -> None:
    config = FakeConfig(values={"heater_sensor_type": "NTC 100K", "heater_max_temp": "150"})
    proxy = ConfigProxy(
        config,
        key_map={
            "sensor_type": "heater_sensor_type",
            "max_temp": "heater_max_temp",
        },
    )

    assert proxy.get("sensor_type") == "NTC 100K"
    assert proxy.getfloat("max_temp") == 150.0
    assert config.accessed == ["heater_sensor_type", "heater_max_temp"]


def test_proxy_overrides_take_precedence_without_accessing_real_config() -> None:
    config = FakeConfig(values={"heater_target_temp": "120"})
    proxy = ConfigProxy(
        config,
        key_map={"inner_max_temp": "heater_target_temp"},
        overrides={"inner_sensor_name": "heater_chamber_element"},
    )

    assert proxy.get("inner_sensor_name") == "heater_chamber_element"
    assert config.accessed == []


def test_proxy_applies_typed_getter_conversions_to_overrides() -> None:
    config = FakeConfig(values={"mapped": "real"})
    proxy = ConfigProxy(
        config,
        key_map={
            "raw": "mapped",
            "float_value": "mapped",
            "int_value": "mapped",
            "enabled": "mapped",
            "disabled": "mapped",
            "choice": "mapped",
            "list_value": "mapped",
            "float_values": "mapped",
            "int_values": "mapped",
            "rows": "mapped",
        },
        overrides={
            "raw": "plain",
            "float_value": "10.5",
            "int_value": "7",
            "enabled": "yes",
            "disabled": False,
            "choice": "pid",
            "list_value": "a, b, c",
            "float_values": "1.5, 2",
            "int_values": ("3", "4"),
            "rows": "a, b\nc, d",
        },
    )

    assert proxy.get("raw") == "plain"
    assert proxy.getfloat("float_value") == 10.5
    assert proxy.getint("int_value") == 7
    assert proxy.getboolean("enabled") is True
    assert proxy.getboolean("disabled") is False
    assert proxy.getchoice("choice", {"pid": "PID"}) == "PID"
    assert proxy.getlist("list_value") == ["a", "b", "c"]
    assert proxy.getfloatlist("float_values") == [1.5, 2.0]
    assert proxy.getintlist("int_values") == [3, 4]
    assert proxy.getlists("rows", seps=(",", "\n")) == [["a", "b"], ["c", "d"]]
    assert config.accessed == []


def test_proxy_override_getfloat_enforces_minval() -> None:
    config = FakeConfig()
    proxy = ConfigProxy(config, overrides={"x": "19.5"})

    with pytest.raises(FakeConfigError, match="x"):
        proxy.getfloat("x", minval=20)

    assert config.accessed == []


@pytest.mark.parametrize("value", ["10", "9.5"])
def test_proxy_override_getfloat_enforces_above(value: str) -> None:
    config = FakeConfig()
    proxy = ConfigProxy(config, overrides={"x": value})

    with pytest.raises(FakeConfigError, match="x"):
        proxy.getfloat("x", above=10)

    assert config.accessed == []


def test_proxy_override_getboolean_rejects_invalid_string() -> None:
    config = FakeConfig()
    proxy = ConfigProxy(config, overrides={"x": "maybe"})

    with pytest.raises(FakeConfigError, match="x"):
        proxy.getboolean("x")

    assert config.accessed == []


def test_proxy_override_getchoice_accepts_list_and_int_key_choices() -> None:
    config = FakeConfig()
    proxy = ConfigProxy(config, overrides={"mode": "pid", "profile": "1"})

    assert proxy.getchoice("mode", ["watermark", "pid"]) == "pid"
    assert proxy.getchoice("profile", {0: "off", 1: "on"}) == "on"
    assert config.accessed == []


def test_proxy_override_list_parsing_honors_separators_parser_and_count() -> None:
    config = FakeConfig()
    proxy = ConfigProxy(
        config,
        overrides={
            "names": "a| b|c",
            "bad_count": "a|b",
            "matrix": "1;2, 3;4",
        },
    )

    assert proxy.getlist("names", sep="|", count=3) == ["a", "b", "c"]
    with pytest.raises(FakeConfigError, match="bad_count"):
        proxy.getlist("bad_count", sep="|", count=3)
    assert proxy.getlists("matrix", seps=(";", ","), parser=int) == [[1, 2], [3, 4]]
    assert config.accessed == []


def test_proxy_applies_key_map_after_override_lookup() -> None:
    config = FakeConfig(values={"heater_target_temp": "120"})
    proxy = ConfigProxy(
        config,
        key_map={"inner_max_temp": "heater_target_temp"},
        overrides={"heater_target_temp": "999"},
    )

    assert proxy.getfloat("inner_max_temp") == 120.0
    assert config.accessed == ["heater_target_temp"]


def test_proxy_name_override_replaces_config_name() -> None:
    config = FakeConfig(name="heater_chamber")
    proxy = ConfigProxy(config, name_override="temperature_sensor heater_chamber_element")

    assert proxy.get_name() == "temperature_sensor heater_chamber_element"


def test_proxy_delegates_non_getter_config_methods() -> None:
    config = FakeConfig(values={"_sections": {"verify_heater heater_chamber"}})
    proxy = ConfigProxy(config)

    proxy.deprecate("old_option")

    assert proxy.getsection("printer") == "section:printer"
    assert proxy.has_section("verify_heater heater_chamber") is True
    assert config.deprecated == ["old_option"]


def test_proxy_deprecate_maps_virtual_option_names() -> None:
    config = FakeConfig()
    proxy = ConfigProxy(config, key_map={"max_temp": "heater_max_temp"})

    proxy.deprecate("max_temp")

    assert config.deprecated == ["heater_max_temp"]


def test_proxy_deprecate_maps_virtual_option_names_and_preserves_value() -> None:
    config = FakeConfig()
    proxy = ConfigProxy(config, key_map={"mode": "heater_mode"})

    proxy.deprecate("mode", "old")

    assert config.deprecated == [("heater_mode", "old")]


def test_proxy_delegates_unknown_attributes_to_real_config() -> None:
    config = FakeConfig()
    config.custom_value = object()
    proxy = ConfigProxy(config)

    assert proxy.custom_value is config.custom_value
