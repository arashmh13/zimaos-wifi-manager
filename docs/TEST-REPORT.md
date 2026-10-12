# Test Report

Everything below was verified on real hardware — a ZimaOS box with an
ath9k (AR9227) 2.4 GHz adapter, NetworkManager-managed, Debian 12 base.
No mocks, no simulated results.

## Environment

| | |
|---|---|
| Board | ZimaOS, Debian 12 base |
| Wi-Fi | AR9227, ath9k driver, 2.4 GHz only |
| Adapter modes | `iw list` reports `* AP` → AP+STA capable |
| NetworkManager | host-owned, keyfiles in `/etc/NetworkManager/system-connections` |
| Container | `network_mode: host`, `NET_ADMIN` + `NET_RAW` |
| Backend | Python 3.11 (Debian 12 image), stdlib only |

## Results

| # | Test | Result |
|---|---|---|
| 1 | Scan returns nearby networks | **PASS** — 16–17 rows with SSID, signal, security, channel |
| 2 | Connect with wrong password | **PASS** — fails cleanly, previous connection restored |
| 3 | Phantom profile forget | **PASS** — forget a non-existent profile is a no-op, no error |
| 4 | Hotspot start (WPA2-AES) | **PASS** — `ap0` up on channel 7, `10.42.0.1/24` |
| 5 | Hotspot stop | **PASS** — clean teardown, `ap0` removed, routes restored |
| 6 | **Simultaneous STA + AP** | **PASS** — `wlan0` stayed associated while `ap0` served clients |
| 7 | NAT / internet sharing | **PASS** — real client got DHCP `10.42.0.117`, pinged `1.1.1.1` through the box |
| 8 | Client visible in UI | **PASS** — real MAC, signal, link rate, lease shown live |
| 9 | Diagnostics output | **PASS** |
| 10 | Internet connectivity probe | **PASS** — reported `true` on live link |
| 11 | Auth bootstrap (random password) | **PASS** — `initial-password.txt` written mode `0600`, no secret in logs |
| 12 | Bad credentials rejected | **PASS** — `401` on wrong password |
| 13 | `/api/ping` public (healthcheck) | **PASS** — `200` without auth |
| 14 | Dashboard tile adoption | **PASS** — tile rendered with name, port 8095, icon, status |
| 15 | UI renders with SSE blocked | **PASS** — jsdom harness: 17 rows, 0 skeletons, 0 JS errors |

### Known findings

- **SSE may be killed by VPNs/proxies.** A long-lived `text/event-stream` can
  be torn down client-side. The frontend therefore falls back to polling
  `/api/jobs/<id>` every 1.2 s with a de-dup set, so results always arrive.
  Verified by loading the real UI with `EventSource` stubbed out.
- **`docker restart` does not adopt a rebuilt image.** It re-runs the same
  container definition. Use `docker rm -f` + `docker run` (the installer does).
- **Container recreation drops the client link.** The saved NM profile stays,
  so `nmcli con up <name> ifname wlan0` restores it; reconnect on next boot.
- **This adapter is 2.4 GHz only.** 5 GHz band selection is rejected by
  NetworkManager; the UI hides the band selector when only one band exists.
- **Single-radio limit.** On adapters without true AP+STA concurrency,
  starting the hotspot may drop the client link. The app detects the state
  and reports it rather than failing silently.

## Reproducing

```bash
# on the box, after install.sh
docker logs -f wifi-manager          # watch for the scan/connect/hotspot ops
curl -u admin:<password> http://127.0.0.1:8095/api/status
curl -u admin:<password> http://127.0.0.1:8095/api/diag | python3 -m json.tool
```
