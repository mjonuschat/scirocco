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
classify_path() {  # echoes: symlink | real | absent  (test -L before -e: dangling links)
  local p=$1
  if [ -L "$p" ]; then
    echo symlink
  elif [ -e "$p" ]; then
    echo real
  else
    echo absent
  fi
}

remove_safe_link() {  # status: 0=removed  1=absent  2=refused(real)  3=rm-failed
  local p=$1
  case "$(classify_path "$p")" in
    symlink) if rm "$p"; then return 0; else return 3; fi ;;
    absent)  return 1 ;;
    real)    return 2 ;;
  esac
}
json_get() {  # read JSON on stdin, walk the given keys, print a string value or empty
  "${JSON_PY}" -c '
import sys, json
try:
    cur = json.load(sys.stdin)
except Exception:
    print(""); sys.exit(0)
for key in sys.argv[1:]:
    if isinstance(cur, dict) and key in cur:
        cur = cur[key]
    else:
        print(""); sys.exit(0)
print(cur if isinstance(cur, str) else "")
' "$@" 2>/dev/null || true
}
fetch_printer_info() { :; }
resolve_klipper_path() { :; }
preflight_checks() { :; }
require_kalico() {  # hard gate: target must support dual_loop_pid
  local heaters="${KLIPPER_PATH}/klippy/extras/heaters.py"
  if [ -f "${heaters}" ] && grep -q "dual_loop_pid" "${heaters}"; then
    return 0
  fi
  if [ "${KALICO_APP:-}" = "Kalico" ] || [ -f "${KLIPPER_PATH}/klippy/extras/danger_options.py" ]; then
    die "Your Kalico is too old — it has no dual_loop_pid control. Update Kalico."
  fi
  die "heater_chamber requires Kalico; this looks like mainline Klipper."
}
check_python_version() { :; }
check_download() {
  if [ -f "${HEATER_CHAMBER_PATH}/heater_chamber/__init__.py" ]; then
    log "[DOWNLOAD] Using existing checkout at ${HEATER_CHAMBER_PATH}"
    return 0
  fi
  if [ ! -e "${HEATER_CHAMBER_PATH}" ] || [ -z "$(ls -A "${HEATER_CHAMBER_PATH}" 2>/dev/null)" ]; then
    log "[DOWNLOAD] Cloning ${REPO_URL} into ${HEATER_CHAMBER_PATH}"
    git clone "${REPO_URL}" "${HEATER_CHAMBER_PATH}" || die "git clone of ${REPO_URL} failed"
    chmod +x "${HEATER_CHAMBER_PATH}/install.sh" 2>/dev/null || true
    return 0
  fi
  die "${HEATER_CHAMBER_PATH} exists but is not a heater_chamber checkout; move it aside or set HEATER_CHAMBER_PATH"
}
plugins_link()  { printf '%s\n' "${KLIPPER_PATH}/klippy/plugins/heater_chamber"; }
extras_link()   { printf '%s\n' "${KLIPPER_PATH}/klippy/extras/heater_chamber"; }

link_extension() {
  local selected other
  if [ -d "${KLIPPER_PATH}/klippy/plugins" ]; then
    selected="$(plugins_link)"; other="$(extras_link)"
  else
    selected="$(extras_link)"; other="$(plugins_link)"
  fi

  # Phase 1: classify both read-only; abort before any change if either is real.
  local p
  for p in "${selected}" "${other}"; do
    if [ "$(classify_path "${p}")" = "real" ]; then
      die "${p} is not a symlink (manually managed?); refusing to overwrite."
    fi
  done

  # Phase 2: both are symlink-or-absent now; clear and create.
  # `if ...; then ... else rc=$?` keeps the capture safe under `set -e`.
  local rc
  for p in "${selected}" "${other}"; do
    if remove_safe_link "${p}"; then rc=0; else rc=$?; fi
    case "${rc}" in
      0|1) : ;;  # removed or absent — fine
      2)   die "${p} is not a symlink (manually managed?); refusing to overwrite." ;;
      *)   die "Failed to remove existing symlink ${p}" ;;
    esac
  done
  ln -s "${HEATER_CHAMBER_PATH}/heater_chamber" "${selected}"
  log "[INSTALL] Linked ${selected}"
}

unlink_extension() {
  local p rc
  for p in "$(plugins_link)" "$(extras_link)"; do
    if remove_safe_link "${p}"; then rc=0; else rc=$?; fi
    case "${rc}" in
      0) log "[UNINSTALL] Removed ${p}" ;;
      1) : ;;  # absent — nothing to report
      2) log "[SKIP] ${p} is not a symlink; leaving it." ;;
      *) log "[WARN] Failed to remove symlink ${p}" ;;
    esac
  done
  return 0
}
add_updater() { :; }
remove_updater() { :; }
check_no_active_print() {  # 0 = safe to restart, 1 = skip (active or unknown)
  local json state
  json="$(curl -fsS --max-time 8 "${MOONRAKER_HOST}/printer/objects/query?print_stats" 2>/dev/null)" || return 1
  state="$(printf '%s' "${json}" | json_get result status print_stats state)"
  case "${state}" in
    standby|complete|cancelled|error) return 0 ;;
    *) return 1 ;;  # printing, paused, unknown, or empty -> skip
  esac
}
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
