#!/usr/bin/env bash
# =============================================================================
# Wi-Fi Manager for ZimaOS / CasaOS — one-shot installer
#
#   curl -fsSL https://raw.githubusercontent.com/arashmh13/zimaos-wifi-manager/main/install.sh | sudo bash
#
# What it does:
#   1. checks Docker + a wireless adapter are present
#   2. fetches the source (git clone, or tarball fallback)
#   3. builds the image (uses cache, so re-runs are fast)
#   4. generates a random admin password (no guessable default)
#   5. runs the container with host networking + NET_ADMIN
#   6. installs the CasaOS/ZimaOS dashboard tile (label-driven)
#   7. prints the URL and the credentials
#
# Idempotent: safe to re-run to upgrade. Rollback: ./uninstall.sh
# =============================================================================
set -euo pipefail

REPO_OWNER="${WM_REPO_OWNER:-arashmh13}"
REPO_NAME="${WM_REPO_NAME:-zimaos-wifi-manager}"
REPO_URL="${WM_REPO_URL:-https://github.com/${REPO_OWNER}/${REPO_NAME}.git}"
BRANCH="${WM_BRANCH:-main}"
IMAGE="${WM_IMAGE:-wifi-manager:latest}"
CONTAINER="${WM_CONTAINER:-wifi-manager}"
PORT="${WM_PORT:-8095}"
DATA_DIR="${WM_DATA_DIR:-/DATA/wifi-manager}"
SRC_DIR="${WM_SRC_DIR:-${DATA_DIR}/src}"

log()  { printf '\033[1;36m[wm]\033[0m %s\n' "$*"; }
ok()   { printf '\033[1;32m[wm]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[wm]\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[1;31m[wm]\033[0m %s\n' "$*" >&2; exit 1; }

# ---------------------------------------------------------------- 0. privileges
[ "$(id -u)" -eq 0 ] || {
  if command -v sudo >/dev/null 2>&1; then
    log "re-running as root via sudo"
    exec sudo -E bash -c "$0 $*" -- "$@"
  fi
  die "run as root (sudo bash install.sh)"
}

# ---------------------------------------------------------------- 1. preflight
log "preflight checks"
command -v docker >/dev/null 2>&1 || die "docker not found — install Docker first"
docker info >/dev/null 2>&1 || die "docker daemon not reachable (is Docker running?)"

# wireless adapter present?
have_wifi=""
if command -v nmcli >/dev/null 2>&1 && nmcli -t -f DEVICE,TYPE dev 2>/dev/null | grep -q ':wifi$'; then
  have_wifi="yes"
  log "wireless adapter: $(nmcli -t -f DEVICE,TYPE dev | awk -F: '$2=="wifi"{printf "%s ",$1}')"
else
  for d in /sys/class/net/*/wireless; do
    [ -d "$d" ] && have_wifi="yes" && log "wireless adapter: $(basename "$(dirname "$d")")" && break
  done
fi
[ -n "$have_wifi" ] || warn "no wireless adapter detected — the app will install but scanning will return nothing"

# --------------------------------------------------------------- 2. fetch source
if [ -d "${SRC_DIR}/.git" ] || [ -f "${SRC_DIR}/backend/server.py" ]; then
  log "source already present at ${SRC_DIR}"
  if [ -d "${SRC_DIR}/.git" ]; then
    log "updating to ${BRANCH}"
    git -C "${SRC_DIR}" fetch --quiet origin "${BRANCH}" 2>/dev/null || true
    git -C "${SRC_DIR}" reset --quiet --hard "origin/${BRANCH}" 2>/dev/null || true
  fi
else
  log "fetching source into ${SRC_DIR}"
  mkdir -p "${SRC_DIR}"
  if command -v git >/dev/null 2>&1 && git clone --quiet --depth 1 --branch "${BRANCH}" "${REPO_URL}" "${SRC_DIR}"; then
    ok "cloned ${REPO_URL}"
  else
    warn "git clone failed — falling back to tarball"
    tmp="$(mktemp -d)"
    curl -fsSL "https://github.com/${REPO_OWNER}/${REPO_NAME}/archive/refs/heads/${BRANCH}.tar.gz" -o "${tmp}/src.tgz" \
      || die "could not download source from ${REPO_OWNER}/${REPO_NAME}"
    tar -xzf "${tmp}/src.tgz" -C "${tmp}"
    cp -a "${tmp}/${REPO_NAME}-${BRANCH}/." "${SRC_DIR}/"
    rm -rf "${tmp}"
    ok "tarball extracted"
  fi
fi
[ -f "${SRC_DIR}/backend/server.py" ] || die "source incomplete: ${SRC_DIR}/backend/server.py missing"

# ------------------------------------------------------------------ 3. build
log "building image ${IMAGE} (cached layers reused)"
docker build -q -t "${IMAGE}" "${SRC_DIR}" >/dev/null
ok "image ready"

# ------------------------------------------------------- 4. admin password
# Precedence: WM_ADMIN_PASSWORD already set → keep it.
# Otherwise generate once and persist, so re-runs don't rotate your password.
PW_FILE="${DATA_DIR}/initial-password.txt"
ADMIN_USER="${WM_ADMIN_USER:-admin}"
if [ -n "${WM_ADMIN_PASSWORD:-}" ]; then
  GEN_PW="${WM_ADMIN_PASSWORD}"
  log "using password from WM_ADMIN_PASSWORD"
elif [ -s "${PW_FILE}" ]; then
  GEN_PW="$(grep '^password:' "${PW_FILE}" | awk '{print $2}')"
  GEN_USER="$(grep '^user:' "${PW_FILE}" | awk '{print $2}')"
  [ -n "${GEN_PW}" ] && ADMIN_USER="${GEN_USER:-$ADMIN_USER}"
  log "keeping existing password from ${PW_FILE}"
else
  GEN_PW="$(head -c 32 /dev/urandom | tr -dc 'A-Za-z0-9' | head -c 20)"
  log "generated a random admin password"
fi
mkdir -p "${DATA_DIR}"
# Always persist the credentials here (root-only). The backend only writes this
# file when IT generates the password, so the installer does it too — that way
# `cat` after a fresh install always works, however the password was chosen.
umask 077
{
  printf 'user: %s\n' "${ADMIN_USER}"
  printf 'password: %s\n' "${GEN_PW}"
} > "${PW_FILE}"
chmod 600 "${PW_FILE}"

# --------------------------------------------------------- 5. stop old container
if docker ps -a --format '{{.Names}}' | grep -qx "${CONTAINER}"; then
  log "replacing existing '${CONTAINER}' container"
  docker rm -f "${CONTAINER}" >/dev/null 2>&1 || true
fi

# ------------------------------------------- 6. CasaOS/ZimaOS + volume mounts
# The dashboard tile is created purely from the container labels below, so the
# CasaOS socket is NOT required — mount it only if it happens to exist.
SOCK="/var/run/casaos/api.sock"
MOUNTS=(
  -v "${DATA_DIR}:${DATA_DIR}"
  -v /etc/NetworkManager/system-connections:/etc/NetworkManager/system-connections
  -v /var/run/dbus:/var/run/dbus
)
if [ -S "${SOCK}" ]; then
  MOUNTS+=(-v "${SOCK}:${SOCK}")
fi
if [ -f /var/run/casaos/app-management.url ] || [ -S "${SOCK}" ]; then
  log "CasaOS/ZimaOS detected — dashboard tile will be created from labels"
else
  log "no CasaOS/ZimaOS detected — app will still be served on :${PORT}"
fi

# ------------------------------------------------------------------- 7. run
log "starting container (host network, port ${PORT})"
docker run -d \
  --name "${CONTAINER}" \
  --network host \
  --cap-add NET_ADMIN \
  --cap-add NET_RAW \
  --device /dev/net/tun:/dev/net/tun \
  -e WM_PORT="${PORT}" \
  -e WM_DATA="${DATA_DIR}" \
  -e WM_ADMIN_USER="${ADMIN_USER}" \
  -e WM_ADMIN_PASSWORD="${GEN_PW}" \
  "${MOUNTS[@]}" \
  --label casaos=casaos \
  --label "name=Wi-Fi Manager" \
  --label "web=${PORT}" \
  --label index=/ \
  --label "icon=http://localhost:${PORT}/icon.svg" \
  --label "desc=Wi-Fi client + hotspot manager for ZimaOS" \
  --restart unless-stopped \
  "${IMAGE}" >/dev/null
ok "container started"

# ------------------------------------------------------------ 8. wait for health
log "waiting for the backend to answer"
up=""
for _ in $(seq 1 40); do
  if curl -fsS -m 2 "http://127.0.0.1:${PORT}/api/ping" >/dev/null 2>&1; then up=yes; break; fi
  sleep 1
done
[ -n "$up" ] || {
  warn "backend not answering yet — last 25 log lines:"
  docker logs --tail 25 "${CONTAINER}" >&2 || true
  die "startup failed"
}
ok "backend healthy on port ${PORT}"

# ------------------------------------------------- 9. verify + CasaOS tile status
# NOTE: do NOT use `hostname -I` — ZimaOS ships a BusyBox-style hostname(1) that
# lacks -I and exits 3, which would kill the script under `set -e`. Ask the
# kernel for the source address of the default route instead.
get_lan_ip() {
  local ip
  ip="$(ip -4 route get 1.1.1.1 2>/dev/null | awk '{for(i=1;i<NF;i++) if($i=="src"){print $(i+1); exit}}')"
  [ -n "$ip" ] || ip="$(ip -4 -o addr show scope global 2>/dev/null | awk '{split($4,a,"/"); print a[1]; exit}')"
  [ -n "$ip" ] || ip="$(hostname -i 2>/dev/null | awk '{print $1}')"
  printf '%s' "$ip"
}

# CasaOS/ZimaOS exposes its app-management port in a file, not always a socket.
detect_mgmt_port() {
  local f p
  for f in /var/run/casaos/app-management.url /run/casaos/app-management.url; do
    [ -f "$f" ] || continue
    p="$(grep -oE ':[0-9]+' "$f" 2>/dev/null | head -1 | tr -d ':')"
    [ -n "$p" ] && { printf '%s' "$p"; return 0; }
  done
  return 1
}

IP="$(get_lan_ip)"
[ -n "${IP}" ] || IP="<box-ip>"

if [ -S /var/run/casaos/api.sock ] || detect_mgmt_port >/dev/null 2>&1; then
  tile_note="dashboard tile installed (labels) — see the ZimaOS home screen"
else
  tile_note="tile skipped (no CasaOS/ZimaOS detected) — open the URL directly"
fi

# --------------------------------------------------------------------- 10. report
printf '\n\033[1;32m'
cat <<EOF
✓ Wi-Fi Manager installed
EOF
printf '\033[0m\n'

cat <<EOF
  URL          : http://${IP}:${PORT}/
  Username     : ${ADMIN_USER}
  Password     : ${GEN_PW}

  Password file: ${PW_FILE}  (root-only)
  Logs         : docker logs -f ${CONTAINER}
  Data         : ${DATA_DIR}

  ${tile_note}

  IMPORTANT: change the password after first login
  (Security card → Change password).

  Upgrade : re-run this script
  Remove  : bash ${SRC_DIR}/uninstall.sh --purge
EOF
