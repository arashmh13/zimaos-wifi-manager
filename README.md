# Wi-Fi Manager for ZimaOS / CasaOS

Scan, connect and forget Wi-Fi networks — and run a hotspot from the same
adapter — all from a tile on your ZimaOS dashboard. No SSH, no terminal.

- **Mode A — Client:** scan, connect (WPA2/WPA3), disconnect, forget, auto-reconnect
- **Mode B — Hotspot:** WPA2-AES/WPA3 AP with DHCP + NAT internet sharing, live client list
- **Simultaneous STA + AP** on a *single* adapter via a virtual `ap0` interface
- Bilingual UI (English / فارسی, full RTL), dark glassmorphism
- HTTP Basic auth on every endpoint, stdlib-only Python backend, no runtime deps
- Automatic pre-change backups of your NetworkManager profiles

---

## Requirements

| | |
|---|---|
| OS | ZimaOS or CasaOS (Debian 12 based), any Linux w/ Docker |
| Docker | 20.10+ |
| Wi-Fi | adapter with `AP` capability (`iw list` → `* AP`), managed by NetworkManager |
| Access | root / sudo on the box |

> **Single-radio caveat:** if your adapter can't do AP+STA at once, the hotspot
> still works but may drop the client link while active. The app detects and
> reports this instead of failing silently.

---

## Install — one script

SSH into your box, then:

```bash
curl -fsSL https://raw.githubusercontent.com/arashmh13/zimaos-wifi-manager/main/install.sh | sudo bash
```

That's it. The script prints your URL and a **randomly generated password** at
the end — save it, then change it from the Security card on first login.

### What the installer does

1. Verifies Docker is running and a wireless adapter exists
2. Clones the source into `/DATA/wifi-manager/src` (tarball fallback if no git)
3. Builds `wifi-manager:latest` (cached layers → re-runs are seconds)
4. Generates a random admin password — **no guessable default**
5. Runs the container: host networking, `NET_ADMIN`, `NET_RAW`
6. Adds the CasaOS/ZimaOS labels that install the dashboard tile
7. Waits for `/api/ping`, then prints URL + credentials

### Install options

| Env var | Default | Meaning |
|---|---|---|
| `WM_PORT` | `8095` | HTTP port |
| `WM_ADMIN_USER` | `admin` | initial username |
| `WM_ADMIN_PASSWORD` | *(random)* | set your own instead of generating |
| `WM_CONTAINER` | `wifi-manager` | container name |
| `WM_DATA_DIR` | `/DATA/wifi-manager` | persistent data |
| `WM_REPO_URL` | this repo | install from a fork |

```bash
# example: custom port + your own password
sudo WM_PORT=9000 WM_ADMIN_PASSWORD='choose-strong' bash install.sh
```

---

## Manual install (docker compose)

```bash
git clone https://github.com/arashmh13/zimaos-wifi-manager.git
cd wifi-manager
sudo docker compose up -d --build
```

---

## Using it

### Connect to a network

1. Open `http://<box-ip>:8095/` (or the dashboard tile) and log in
2. The **Available networks** card auto-scans on load
3. Click a network → enter the password → **Connect**
4. Wrong password? Nothing breaks — your previous connection is restored
   automatically and the error is shown in plain language

The **Wi-Fi client** card shows live SSID, signal, IP, iface, link rate and
internet reachability.

### Start a hotspot

The **Hotspot** card lets you set SSID, password, channel and subnet, then
toggle it on. Clients get DHCP on `10.42.0.1/24` and share the box's upstream
connection via NAT. Connected clients are listed live.

> The hotspot is always WPA2-AES or WPA3. There is no unsecured mode.

### Safety

Every connect attempt snapshots your NM profiles + firewall state to
`/DATA/wifi-manager/backup/<tag>-<timestamp>/` first, so a mistake is
reversible without shell access.

---

## ZimaOS dashboard tile

The tile is installed automatically via Docker labels — no frontend hacking:

```yaml
labels:
  casaos: casaos      # the trigger CasaOS app-management looks for
  name: Wi-Fi Manager
  web: "8095"
  index: /
  icon: http://localhost:8095/icon.svg
  desc: Wi-Fi client + hotspot manager for ZimaOS
```

If the tile doesn't appear, reload the dashboard once. On CasaOS versions that
need an explicit registration, the installer also detects the dynamic
app-management port from `/var/run/casaos/app-management.url`.

---

## Upgrade / Uninstall

```bash
# upgrade — idempotent, keeps your settings and password
curl -fsSL https://raw.githubusercontent.com/arashmh13/zimaos-wifi-manager/main/install.sh | sudo bash

# remove app, keep data/backups
sudo bash /DATA/wifi-manager/src/uninstall.sh

# remove everything including backups
sudo bash /DATA/wifi-manager/src/uninstall.sh --purge
```

Your NetworkManager profiles are never deleted, so the box stays on whatever
network it was using.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `Connection timed out` on `:8095` | `docker logs wifi-manager` — check the port isn't taken |
| Scan returns nothing | adapter may lack AP/scan support; `iw list` to confirm |
| Hotspot fails to start | needs `NET_ADMIN`; confirm the run used `--network host` |
| Tile missing from dashboard | verify labels with `docker inspect wifi-manager`, reload UI |
| `nmcli` errors in logs | host NetworkManager must own `wlan0` (not wicd/iwd) |
| UI shows stale data | assets are cache-busted (`?v=N`); hard-refresh once |

Logs: `docker logs -f wifi-manager`
Data: `/DATA/wifi-manager/` (`data/`, `backup/`, `logs/`, `initial-password.txt`)

---

## Security notes

- Every API endpoint requires HTTP Basic auth except `/api/ping` and `/icon.svg`
- Passwords are stored as PBKDF2-style salted SHA-256, never in plaintext
- PSKs and passwords are **never** written to logs, events, responses or job history
- Actions are whitelisted — there is no arbitrary-command endpoint
- Input is strictly validated (SSID/PSK length + charset, channel, subnet, name)
- Bind to a trusted LAN. Don't expose port 8095 to the internet.

## Tested on

- ZimaOS (Debian 12 base) · ath9k AR9227 (2.4 GHz) · NetworkManager
- Simultaneous STA+AP verified: hotspot up on `ap0` while `wlan0` stayed
  associated, with DHCP + NAT internet sharing confirmed from a real client

## License

[MIT](LICENSE)
