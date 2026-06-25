# Heater Chamber

`heater_chamber` is a Kalico plugin for an actively heated print chamber.
One config section owns the element sensor, chamber sensor, heater, and
circulation fan.

## Install

Symlink the package directory into Kalico plugins:

```bash
ln -s /path/to/heater_chamber/heater_chamber /path/to/kalico/klippy/plugins/heater_chamber
```

## Instances

The default instance is loaded from:

```ini
[heater_chamber]
```

Named instances are loaded from:

```ini
[heater_chamber rear]
```

The default instance registers M141 and M191 and reports as `C:` in M105 through
the heater infrastructure. Named instances are controlled with:

```gcode
SET_HEATER_TEMPERATURE HEATER=rear TARGET=55
```

## Safety

`control: dual_loop_pid` is required. The outer loop controls chamber ambient
temperature. The inner loop caps element temperature at `heater_target_temp`.
Kalico `verify_heater` remains responsible for runaway detection.

The fan uses `fan_shutdown_speed: 1.0` by default so it runs at full speed during
firmware shutdown/error.

## Example

```ini
[heater_chamber]
heater_pin: PD12
#heater_max_power: 1.0
heater_sensor_type: Generic 3950
heater_sensor_pin: PF4
heater_min_temp: 0
heater_max_temp: 150
#heater_pullup_resistor: 4700
#heater_inline_resistor: 0

chamber_sensor_type: Generic 3950
chamber_sensor_pin: PF5
chamber_min_temp: 0
chamber_max_temp: 80
#chamber_pullup_resistor: 4700
#chamber_inline_resistor: 0

control: dual_loop_pid
pid_Kp: 10.0
pid_Ki: 0.1
pid_Kd: 30.0

inner_pid_Kp: 20.0
inner_pid_Ki: 1.5
inner_pid_Kd: 80.0

heater_target_temp: 120.0

fan_pin: PD13
#fan_speed: 1.0
#fan_speed_control: false
#fan_heater_temp: 50.0
#fan_shutdown_speed: 1.0
#fan_kick_start_time:
#fan_min_power:
#fan_max_power:
#fan_cycle_time:
#fan_hardware_pwm:
#fan_enable_pin:
#fan_initial_speed:
#fan_tachometer_pin:
#fan_tachometer_ppr:
#fan_tachometer_poll_interval:
```

## Sensor options

Both sensors take the usual Kalico temperature options, prefixed by which
sensor they configure. `heater_*` configures the element sensor (inner loop);
`chamber_*` configures the chamber ambient sensor (outer loop):

| Element sensor | Chamber sensor | Maps to |
| --- | --- | --- |
| `heater_pullup_resistor` | `chamber_pullup_resistor` | `pullup_resistor` |
| `heater_inline_resistor` | `chamber_inline_resistor` | `inline_resistor` |
| `heater_sensor_list` | `chamber_sensor_list` | `sensor_list` |
| `heater_combination_method` | `chamber_combination_method` | `combination_method` |
| `heater_maximum_deviation` | `chamber_maximum_deviation` | `maximum_deviation` |

The last three enable `sensor_type: temperature_combined`. For example, to drive
the chamber loop from the mean of two probes:

```ini
chamber_sensor_type: temperature_combined
chamber_sensor_list: temperature_sensor left, temperature_sensor right
chamber_combination_method: mean
chamber_maximum_deviation: 5.0
chamber_min_temp: 0
chamber_max_temp: 80
```

`heater_max_power` caps the PWM duty on `heater_pin` (default `1.0`). The fan
takes the matching `fan_max_power`.

`fan_speed` sets the operating speed used while the chamber fan is active
(default `1.0`). The fan is active while the chamber heater has a target, or
while the heater element sensor is at or above `fan_heater_temp`.

Set `fan_speed_control: true` to opt an instance into Klipper's `SET_FAN_SPEED`
mux command. This changes the operating speed; the automatic active/idle logic
still decides whether the fan output should be that speed or off.

## G-codes

```gcode
M141 S55
```

Sets the chamber target to 55 C without waiting.

```gcode
M191 S55
```

Sets the chamber target to 55 C and waits only when the chamber is below 55 C.

```gcode
M191 R55
```

Sets the chamber target to 55 C and waits for heating or cooling. If both `S`
and `R` are present, `R` takes precedence.

```gcode
SET_FAN_SPEED FAN=heater_chamber SPEED=0.65
```

When `fan_speed_control: true` is set, changes the default instance's chamber
fan operating speed to 65%. For named instances, use the instance suffix:

```gcode
SET_FAN_SPEED FAN=rear SPEED=0.65
```

If `SPEED=0` is set while the chamber fan should be active, the command is
accepted and a warning is printed to the console.
