#!/usr/bin/env bash
# Wi-Fi Manager — uninstaller. Removes the container + image, keeps your data
# (profiles/backups) unless you pass --purge.
#
#   sudo bash uninstall.sh            # remove app, keep /DATA/wifi-manager
#   sudo bash uninstall.sh --purge    # also delete data + backups
#
# It does NOT touch your Wi-Fi connections: NetworkManager profiles stay
# intact, so the box keeps whatever network it was on.
set -euo pipefail

IMAGE="${WM_IMAGE:-wifi-manager:latest}"
CONTAINER="${WM_CONTAINER:-wifi-manager}"
DATA_DIR="${WM_DATA_DIR:-/DATA/wifi-manager}"
PURGE=0
[ "${1:-}" = "--purge" ] && PURGE=1

log()  { printf '\033[1;36m[wm]\033[0m %s\n' "$*"; }
ok()   { printf '\033[1;32m[wm]\033[0m %s\n' "$*"; }

[ "$(id -u)" -eq 0 ] || exec sudo -E bash "$0" "$@"

if docker ps -a --format '{{.Names}}' | grep -qx "${CONTAINER}"; then
  log "removing container ${CONTAINER}"
  docker rm -f "${CONTAINER}" >/dev/null 2>&1 || true
  ok "container removed"
else
  log "container ${CONTAINER} not present"
fi

if docker image inspect "${IMAGE}" >/dev/null 2>&1; then
  log "removing image ${IMAGE}"
  docker rmi "${IMAGE}" >/dev/null 2>&1 || true
  ok "image removed"
fi

if [ "${PURGE}" -eq 1 ]; then
  log "purging ${DATA_DIR} (backups included)"
  rm -rf "${DATA_DIR}"
  ok "data removed"
else
  log "keeping ${DATA_DIR} (use --purge to delete)"
fi

log "done — Wi-Fi connections were not modified"
