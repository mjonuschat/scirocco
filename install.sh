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
fetch_printer_info() {
  curl -fsS --max-time 8 "${MOONRAKER_HOST}/printer/info" 2>/dev/null || true
}

resolve_klipper_path() {  # uninstall path: discover from Moonraker if unset, else default. Never gates.
  if [ -z "${KLIPPER_PATH:-}" ]; then
    local kp; kp="$(fetch_printer_info | json_get result klipper_path)"
    [ -n "${kp}" ] && KLIPPER_PATH="${kp}"
  fi
  : "${KLIPPER_PATH:=${HOME}/klipper}"
}

preflight_checks() {
  # INSTALL_UID is overridable in tests; bash makes EUID readonly so it can't be faked.
  [ "${INSTALL_UID:-$(id -u)}" -eq 0 ] && die "Do not run this script as root."

  if ! systemctl list-unit-files klipper.service 2>/dev/null | grep -q 'klipper.service'; then
    die "Klipper service not found — install Klipper/Kalico first."
  fi

  local info
  info="$(fetch_printer_info)"
  KALICO_APP="$(printf '%s' "${info}" | json_get result app)"
  local discovered_klipper discovered_py
  discovered_klipper="$(printf '%s' "${info}" | json_get result klipper_path)"
  discovered_py="$(printf '%s' "${info}" | json_get result python_path)"

  if [ -z "${KLIPPER_PATH:-}" ] && [ -n "${discovered_klipper}" ]; then
    KLIPPER_PATH="${discovered_klipper}"
  fi
  : "${KLIPPER_PATH:=${HOME}/klipper}"

  local py="${discovered_py:-${HOME}/klippy-env/bin/python}"
  check_python_version "${py}"

  require_kalico

  KLIPPER_PLUGINS_PATH="${KLIPPER_PATH}/klippy/extras"
  [ -d "${KLIPPER_PATH}/klippy/plugins" ] && KLIPPER_PLUGINS_PATH="${KLIPPER_PATH}/klippy/plugins"
  log "[PRE-CHECK] Target: ${KLIPPER_PATH} (link dir: ${KLIPPER_PLUGINS_PATH})"
}
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
check_python_version() {  # $1 = interpreter path; require >= 3.11
  local py=$1 code
  code="$("${py}" -c 'import sys; print(sys.version_info[0]*100+sys.version_info[1])' 2>/dev/null || true)"
  case "${code}" in
    ''|*[!0-9]*) die "Could not determine Python version for ${py}" ;;
  esac
  if [ "${code}" -lt 311 ]; then
    die "heater_chamber needs Python >= 3.11, but ${py} reports $((code/100)).$((code%100))."
  fi
}
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
add_updater() {
  if [ ! -f "${MOONRAKER_CONFIG}" ]; then
    log "[WARN] ${MOONRAKER_CONFIG} not found; skipping update_manager block."
    return 0
  fi
  if grep -q "update_manager heater_chamber" "${MOONRAKER_CONFIG}"; then
    log "[UPDATER] update_manager block already present; skipping."
    return 0
  fi
  local path_display="${HEATER_CHAMBER_PATH}"
  case "${path_display}" in
    "${HOME}"/*) path_display="~${path_display#${HOME}}" ;;
  esac
  {
    printf '\n%s\n' "${SENTINEL_START}"
    printf '[update_manager heater_chamber]\n'
    printf 'type: git_repo\n'
    printf 'path: %s\n' "${path_display}"
    printf 'origin: %s\n' "${REPO_URL}"
    printf 'managed_services: klipper\n'
    printf 'primary_branch: main\n'
    printf '%s\n' "${SENTINEL_END}"
  } >> "${MOONRAKER_CONFIG}"
  log "[UPDATER] Added update_manager block to ${MOONRAKER_CONFIG}"
}

remove_updater() {
  [ -f "${MOONRAKER_CONFIG}" ] || return 0
  local tmp; tmp="$(mktemp "${TMPDIR:-/tmp}/hc.XXXXXX")"  # explicit template: portable across GNU/BSD mktemp
  awk -v s="${SENTINEL_START}" -v e="${SENTINEL_END}" '
    $0==s { skip=1 }
    !skip { print }
    $0==e { skip=0 }
  ' "${MOONRAKER_CONFIG}" > "${tmp}"
  mv "${tmp}" "${MOONRAKER_CONFIG}"
  log "[UPDATER] Removed update_manager block from ${MOONRAKER_CONFIG}"
}
check_no_active_print() {  # 0 = safe to restart, 1 = skip (active or unknown)
  local json state
  json="$(curl -fsS --max-time 8 "${MOONRAKER_HOST}/printer/objects/query?print_stats" 2>/dev/null)" || return 1
  state="$(printf '%s' "${json}" | json_get result status print_stats state)"
  case "${state}" in
    standby|complete|cancelled|error) return 0 ;;
    *) return 1 ;;  # printing, paused, unknown, or empty -> skip
  esac
}
restart_klipper() {
  if check_no_active_print; then
    log "[POST-INSTALL] Restarting Klipper..."
    sudo systemctl restart klipper
  else
    log "[NOTICE] A print job is active (or print state could not be confirmed). Skipping Klipper restart. Run 'sudo systemctl restart klipper' once the printer is idle to activate the change."
  fi
}

main() {
  resolve_config
  local action="${1:-install}"
  case "${action}" in
    install)
      preflight_checks
      check_download
      link_extension
      add_updater
      restart_klipper
      log "[DONE] heater_chamber installed."
      ;;
    uninstall)
      resolve_klipper_path   # install resolves KLIPPER_PATH in preflight; uninstall needs it too
      unlink_extension
      remove_updater
      restart_klipper
      log "[DONE] heater_chamber uninstalled."
      ;;
    *) die "usage: install.sh [install|uninstall]" ;;
  esac
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  main "$@"
fi
