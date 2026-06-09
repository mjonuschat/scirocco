#!/bin/bash
set -eu
export LC_ALL=C

# ---- configuration (environment-overridable) -----------------------------
: "${MOONRAKER_HOST:=http://localhost:7125}"
: "${REPO_URL:=https://github.com/mjonuschat/scirocco.git}"
: "${JSON_PY:=python3}"
SENTINEL_START="# >>> heater_chamber >>>"
SENTINEL_END="# <<< heater_chamber <<<"

# ---- logging -------------------------------------------------------------
log() { printf '%s\n' "$*"; }
err() { printf '%s\n' "$*" >&2; }
die() { err "[ERROR] $*"; exit 1; }

# ---- helpers -------------------------------------------------------------
abspath() {  # print absolute path of $1 without requiring it to exist
  case "$1" in
    /*) printf '%s\n' "$1" ;;
    *)  printf '%s\n' "$(pwd)/$1" ;;
  esac
}

script_dir() {  # directory containing this script — subshell so the caller's CWD is unchanged
  ( cd "$(dirname "${BASH_SOURCE[0]}")" && pwd )
}

resolve_config() {  # set HEATER_CHAMBER_PATH and MOONRAKER_CONFIG defaults
  local sd; sd="$(script_dir)"
  if [ -z "${HEATER_CHAMBER_PATH:-}" ]; then
    if [ -f "${sd}/heater_chamber/__init__.py" ]; then
      HEATER_CHAMBER_PATH="${sd}"
    else
      HEATER_CHAMBER_PATH="${HOME}/scirocco"
    fi
  fi
  HEATER_CHAMBER_PATH="$(abspath "${HEATER_CHAMBER_PATH}")"
  if [ -z "${MOONRAKER_CONFIG:-}" ]; then
    if [ -f "${HOME}/printer_data/config/moonraker.conf" ]; then
      MOONRAKER_CONFIG="${HOME}/printer_data/config/moonraker.conf"
    else
      MOONRAKER_CONFIG="${HOME}/klipper_config/moonraker.conf"
    fi
  fi
}

# ---- function stubs (implemented in later tasks) -------------------------
classify_path() { :; }
remove_safe_link() { :; }
json_get() { :; }
fetch_printer_info() { :; }
resolve_klipper_path() { :; }
preflight_checks() { :; }
require_kalico() { :; }
check_python_version() { :; }
check_download() { :; }
link_extension() { :; }
unlink_extension() { :; }
add_updater() { :; }
remove_updater() { :; }
check_no_active_print() { :; }
restart_klipper() { :; }

main() {
  resolve_config
  local action="${1:-install}"
  case "${action}" in
    # The install/uninstall sequences are wired in Task 8, once every step function
    # is real. Until then the entrypoint REFUSES to run rather than exit 0 having
    # done nothing — no commit ships an install.sh that silently no-ops.
    install|uninstall) die "install.sh is still being built; '${action}' is not wired yet." ;;
    *) die "usage: install.sh [install|uninstall]" ;;
  esac
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  main "$@"
fi
