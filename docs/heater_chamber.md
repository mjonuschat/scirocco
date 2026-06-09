# Heater Chamber

`heater_chamber` is a Kalico extras module for an actively heated print chamber.
One config section owns the element sensor, chamber sensor, heater, and
circulation fan.

## Install

Symlink the package directory into Kalico/Klipper extras:

```bash
ln -s /path/to/heater_chamber/heater_chamber /path/to/kalico/klippy/extras/heater_chamber
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
heater_sensor_type: NTC 100K beta 3950
heater_sensor_pin: PF4
heater_min_temp: 0
heater_max_temp: 150

chamber_sensor_type: NTC 100K beta 3950
chamber_sensor_pin: PF5
chamber_min_temp: 0
chamber_max_temp: 80

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
