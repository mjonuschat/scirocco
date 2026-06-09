# Scirocco

Kalico extension module for controlling an active chamber heater with dual-loop
PID, integrated circulation fan control, and Marlin-compatible M141/M191
G-codes.

## Development

Use Python 3.11 or newer.

```bash
python3.11 -m pip install -e ".[dev]"
python3.11 -m pytest -q
python3.11 -m ruff format --check .
python3.11 -m ruff check .
```

## Install

Symlink the package directory into Kalico/Klipper extras:

```bash
ln -s /path/to/heater_chamber/heater_chamber /path/to/kalico/klippy/extras/heater_chamber
```
