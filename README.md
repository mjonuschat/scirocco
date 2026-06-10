# Scirocco

Kalico extension module for controlling an active chamber heater with dual-loop
PID, integrated circulation fan control, and Marlin-compatible M141/M191
G-codes.

## Example config

```ini
[heater_chamber]
heater_pin: <CHAMBER_HEATER>
heater_sensor_type: Generic 3950
heater_sensor_pin: <CHAMBER_HEATER_TEMPERATURE>
heater_min_temp: 0
heater_max_temp: 180
heater_target_temp: 150.0          # inner-loop cap: element never exceeds this

chamber_sensor_type: Generic 3950
chamber_sensor_pin: <CHAMBER_TEMPERATURE>
chamber_min_temp: 0
chamber_max_temp: 80

fan_pin: <CHAMBER_HEATER_FAN>

control: dual_loop_pid

# outer loop: chamber temp → inner heater target
pid_Kp: 20.0
pid_Ki: 0.005
pid_Kd: 500.0

# inner loop: element temp → PWM
inner_pid_Kp: 25.0
inner_pid_Ki: 1.0
inner_pid_Kd: 80.0
```

PID values need tuning per setup. Run `PID_CALIBRATE HEATER=heater_chamber
TARGET=<your_target>` once installed. See [`docs/heater_chamber.md`](docs/heater_chamber.md)
for all options including the `temperature_combined` multi-sensor setup.

## Development

Use Python 3.11 or newer.

```bash
python3.11 -m pip install -e ".[dev]"
python3.11 -m pytest -q
python3.11 -m ruff format --check .
python3.11 -m ruff check .
```

## Install

On the Kalico host (not as root):

```bash
curl -fsSL https://raw.githubusercontent.com/mjonuschat/scirocco/main/install.sh | bash
```

Or manually:

```bash
cd ~
git clone https://github.com/mjonuschat/scirocco.git
cd scirocco
./install.sh
```

The installer clones the repo to `~/scirocco` if it isn't there already,
links the extension into Kalico, adds a Moonraker `update_manager` block, and
restarts Klipper (skipping the restart if a print is in progress). It requires
Kalico with the `dual_loop_pid` control and Python 3.11+.

To uninstall:

```bash
~/scirocco/install.sh uninstall
```

Override defaults with environment variables, e.g. `KLIPPER_PATH`,
`HEATER_CHAMBER_PATH`, `MOONRAKER_CONFIG`, `MOONRAKER_HOST`.

## Troubleshooting

### Klipper shuts down with "not heating at expected rate"

Klipper's built-in `verify_heater` watchdog checks that the heater reaches its
target within a fixed time window. Chamber heaters are slow by design — large
thermal mass, low wattage — so the defaults that work for a hotend can trip on
a chamber heater.

If Klipper shuts down with `Heater heater_chamber not heating at expected rate`,
add a `[verify_heater]` override tuned for the slower response:

```ini
[verify_heater heater_chamber]
check_gain_time: 240   # seconds allowed to gain heating_gain degrees
max_error: 240         # accumulated error budget before shutdown
heating_gain: 0.1      # minimum degrees gained per check_gain_time
```

Adjust `check_gain_time` to match how long your chamber actually takes to show
measurable temperature rise after power-on.

## Disclaimer

This software controls real heating hardware. Improper configuration, electrical
faults, or software bugs can cause fire, property damage, or injury.

**Use entirely at your own risk.** The authors provide this software as-is,
without warranty of any kind, express or implied. In no event shall the authors
be liable for any damages — including but not limited to property damage, data
loss, or personal injury — arising from the use or inability to use this
software.

You are responsible for ensuring your installation is electrically safe, thermally
protected, and compliant with local regulations. Never leave an actively heated
enclosure unattended without independent thermal protection.
