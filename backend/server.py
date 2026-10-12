#!/usr/bin/env python3
"""ZimaOS Wi-Fi Manager — privileged backend (stdlib only).

Restricted JSON API + SSE for the Wi-Fi Manager dashboard app.
Runs as root via systemd (wifi-manager.service) on the ZimaOS host.

Security model:
  * HTTP Basic auth on every endpoint except /icon.svg (tile icon).
  * Strict action whitelist — no arbitrary command/shell execution ever;
    every external call is an argv list to a fixed binary (nmcli/iw/ip/...).
  * Strict input validation (SSID/PSK/channel/subnet/name), length + charset.
  * Passwords/PSKs are never written to logs, events or responses.
  * LAN-only usage assumed; not exposed to the internet.

Data locations (persistent): /DATA/wifi-manager/{config,auth,logs,backup,state}
"""
import base64
import hmac
import hashlib
import ipaddress
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import threading
import time
import traceback
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from queue import Empty, Queue
from urllib.parse import urlparse, parse_qs, unquote

VERSION = "1.0.0"
# Data dir is overridable via WM_DATA (set by Dockerfile/compose/install.sh);
# default matches the ZimaOS/CasaOS persistent-storage convention.
BASE = os.environ.get("WM_DATA", "/DATA/wifi-manager").rstrip("/") or "/DATA/wifi-manager"
# Static files: docker image ships them in /app/web; native installs can set WM_WEB.
_default_web = "/app/web" if os.path.isdir("/app/web") else os.path.join(BASE, "web")
WEB = os.environ.get("WM_WEB") or _default_web
CFG_PATH = os.path.join(BASE, "config.json")
AUTH_PATH = os.path.join(BASE, "auth.json")
STATE_PATH = os.path.join(BASE, "state.json")
LOG_PATH = os.path.join(BASE, "logs", "backend.log")
HOTSPOT_CON = "WifiManager-Hotspot"
PORT = int(os.environ.get("WM_PORT", 8095))
MAX_BODY = 8192
SSID_ESC = {"max_len": 32}
PSK_ESC = {"min_len": 8, "max_len": 63}
SCAN_CACHE_TTL = 3.0

# ----------------------------------------------------------------------------- logging

_log_lock = threading.Lock()
_events = deque(maxlen=300)


def log(evt, level="info", **kw):
    rec = {"t": round(time.time(), 2), "evt": evt, "level": level}
    rec.update(kw)
    line = json.dumps(rec, ensure_ascii=False)
    with _log_lock:
        _events.append(rec)
        try:
            os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
            if os.path.exists(LOG_PATH) and os.path.getsize(LOG_PATH) > 1_000_000:
                os.replace(LOG_PATH, LOG_PATH + ".1")
            with open(LOG_PATH, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception:
            pass
    broadcast("log", rec)


# ----------------------------------------------------------------------------- helpers

class AppError(Exception):
    def __init__(self, code, message, http=400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.http = http


def run(args, timeout=30, env=None):
    """Run a fixed binary with argv list. Never uses a shell."""
    try:
        p = subprocess.run(
            [str(a) for a in args],
            capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=timeout, env=env,
        )
        return p.returncode, (p.stdout or ""), (p.stderr or "")
    except subprocess.TimeoutExpired:
        return -9, "", "timeout"
    except FileNotFoundError as e:
        return -1, "", str(e)
    except Exception as e:  # pragma: no cover
        return -1, "", str(e)


def nmcli(args, timeout=30):
    return run(["nmcli", "--wait", str(timeout)] + list(args), timeout=timeout + 5)


def split_terse(line):
    out, buf, esc = [], [], False
    for ch in line:
        if esc:
            buf.append(ch)
            esc = False
        elif ch == "\\":
            esc = True
        elif ch == ":":
            out.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    out.append("".join(buf))
    return out


def unesc(v):
    return re.sub(r"\\(.)", lambda m: {"n": "\n"}.get(m.group(1), m.group(1)), v)


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def freq_to_channel(f):
    try:
        f = int(float(f))
    except Exception:
        return None
    if 2412 <= f <= 2472:
        return (f - 2407) // 5
    if f == 2484:
        return 14
    if 5180 <= f <= 5885:
        return (f - 5000) // 5
    return None


def signal_quality(dbm):
    try:
        dbm = int(float(dbm))
    except Exception:
        return 0
    return clamp(int((dbm + 100) * 2), 0, 100)


# ----------------------------------------------------------------------------- validation

def validate_ssid(s):
    if not isinstance(s, str):
        raise AppError("bad_ssid", "SSID must be a string")
    b = s.encode("utf-8")
    if not (1 <= len(b) <= SSID_ESC["max_len"]):
        raise AppError("bad_ssid", "SSID must be 1-32 bytes")
    if any(ord(c) < 0x20 or ord(c) == 0x7F for c in s):
        raise AppError("bad_ssid", "SSID contains control characters")
    if s.strip() == "":
        raise AppError("bad_ssid", "SSID cannot be empty")
    return s


def validate_psk(p, allow_open=False, required=True):
    if p is None or p == "":
        if required and not allow_open:
            raise AppError("bad_psk", "Password required (8-63 characters)")
        return None
    if not isinstance(p, str):
        raise AppError("bad_psk", "Password must be a string")
    if not (PSK_ESC["min_len"] <= len(p) <= PSK_ESC["max_len"]):
        raise AppError("bad_psk", "Password must be 8-63 characters")
    if any(ord(c) < 0x20 or ord(c) > 0x7E for c in p):
        raise AppError("bad_psk", "Password must be printable ASCII (no spaces at ends)")
    if p != p.strip():
        raise AppError("bad_psk", "Password must not start/end with whitespace")
    return p


def validate_channel(c):
    if c in (None, "", "auto"):
        return None
    try:
        c = int(c)
    except Exception:
        raise AppError("bad_channel", "Channel must be an integer 1-13")
    if not (1 <= c <= 13):
        raise AppError("bad_channel", "Channel must be 1-13 (2.4 GHz)")
    return c


def validate_subnet(s):
    if s in (None, ""):
        return "10.42.0.1/24"
    try:
        net = ipaddress.ip_interface(s)
    except Exception:
        raise AppError("bad_subnet", "Subnet must look like 10.42.0.1/24")
    if net.version != 4:
        raise AppError("bad_subnet", "IPv4 subnet required")
    if net.network.prefixlen not in (24, 23, 25, 16, 22, 26):
        raise AppError("bad_subnet", "Use a /16-/26 prefix")
    # no overlap with existing on-link routes
    rc, out, _ = run(["ip", "-4", "-o", "route", "show", "link"], timeout=10)
    if rc == 0:
        for line in out.splitlines():
            parts = line.split()
            if not parts:
                continue
            try:
                exist = ipaddress.ip_network(parts[0], strict=False)
            except Exception:
                continue
            if exist.version == 4 and net.network.overlaps(exist):
                raise AppError("subnet_overlap", f"Subnet overlaps existing network {exist}")
    return str(net)


def validate_security(sec):
    if sec in (None, "", "wpa2"):
        return "wpa-psk"
    if sec in ("wpa3", "sae"):
        return "sae"
    raise AppError("bad_security", "Security must be wpa2 or wpa3")


def validate_con_name(name, wifi_names):
    """Forget/disconnect targets must exactly match a known saved Wi-Fi connection."""
    if not isinstance(name, str) or name not in wifi_names:
        raise AppError("unknown_network", "Unknown saved network")
    return name


# ----------------------------------------------------------------------------- system state

_sys_lock = threading.Lock()
_status_cache = {"t": 0, "data": None}
_internet_cache = {"t": 0, "ok": None}
_iface = None
_caps = None
_mode = None  # 'simultaneous' | 'exclusive' | None  (hotspot mode actually running)


def wifi_iface():
    global _iface
    if _iface:
        return _iface
    rc, out, _ = run(["nmcli", "-t", "-f", "DEVICE,TYPE,STATE,CONNECTION", "dev"], timeout=10)
    if rc == 0:
        for line in out.splitlines():
            f = [unesc(x) for x in split_terse(line)]
            if len(f) >= 2 and f[1] == "wifi" and not f[0].startswith(("p2p-", "ap")):
                _iface = f[0]
                return _iface
    _iface = "wlan0"
    return _iface


def phy_name(iface):
    p = f"/sys/class/net/{iface}/phy80211"
    try:
        return os.path.basename(os.readlink(p))
    except Exception:
        return "phy0"


def get_caps():
    global _caps
    if _caps is not None:
        return _caps
    phy = phy_name(wifi_iface())
    rc, out, _ = run(["iw", "phy", phy, "info"], timeout=15)
    txt = out if rc == 0 else ""
    combos = ""
    m = re.search(r"valid interface combinations:(.*?)HT Capability overrides:", txt, re.S)
    if m:
        combos = m.group(1)
    bands = []
    if re.search(r"Band 1:", txt):
        bands.append("2.4GHz")
    if re.search(r"Band 2:", txt):
        bands.append("5GHz")
    _caps = {
        "iface": wifi_iface(),
        "phy": phy,
        "band": bands or ["2.4GHz"],
        "five_ghz": "5GHz" in bands,
        "ap_mode": bool(re.search(r"\*\s*AP\b", txt)) and " * AP" in txt,
        "simultaneous": ("#{ managed" in combos and "#{ AP" in combos),
        "single_channel": "#channels <= 1" in combos,
        "wpa3_client": "supports SAE" in txt,
        "driver": driver_of(wifi_iface()),
        "combos": " ".join(combos.split()),
    }
    return _caps


def driver_of(iface):
    # sysfs works everywhere and needs no extra tools
    try:
        return os.path.basename(
            os.path.realpath("/sys/class/net/%s/device/driver" % iface))
    except OSError:
        pass
    rc, out, _ = run(["ethtool", "-i", iface], timeout=8)
    if rc == 0:
        for line in out.splitlines():
            if line.startswith("driver:"):
                return line.split(":", 1)[1].strip()
    return "unknown"


def wlan_link():
    """Parse `iw dev <iface> link`."""
    iface = wifi_iface()
    rc, out, _ = run(["iw", "dev", iface, "link"], timeout=10)
    info = {"connected": False, "ssid": None, "bssid": None, "freq": None,
            "channel": None, "signal": None, "quality": 0, "rx_rate": None, "tx_rate": None}
    if rc != 0:
        return info
    if "Not connected" in out:
        return info
    info["connected"] = True
    for line in out.splitlines():
        s = line.strip()
        if s.startswith("Connected to"):
            m = re.match(r"Connected to ([0-9a-f:]{17})", s)
            if m:
                info["bssid"] = m.group(1)
        elif s.startswith("SSID:"):
            info["ssid"] = unesc(s.split(":", 1)[1].strip())
        elif s.startswith("freq:"):
            try:
                info["freq"] = float(s.split(":", 1)[1].strip())
            except Exception:
                pass
        elif s.startswith("signal:"):
            m = re.search(r"(-?\d+)", s)
            if m:
                info["signal"] = int(m.group(1))
        elif s.startswith("rx bitrate:"):
            info["rx_rate"] = s.split(":", 1)[1].strip()
        elif s.startswith("tx bitrate:"):
            info["tx_rate"] = s.split(":", 1)[1].strip()
    if info["freq"]:
        info["channel"] = freq_to_channel(info["freq"])
        info["band"] = "5GHz" if info["freq"] > 3000 else "2.4GHz"
    if info["signal"] is not None:
        info["quality"] = signal_quality(info["signal"])
    return info


def iface_ipv4(iface):
    rc, out, _ = run(["ip", "-4", "-o", "addr", "show", "dev", iface], timeout=8)
    if rc != 0:
        return None
    m = re.search(r"inet (\d+\.\d+\.\d+\.\d+)/(\d+)", out)
    if m:
        return {"ip": m.group(1), "prefix": int(m.group(2))}
    return None


def default_route():
    rc, out, _ = run(["ip", "route", "show", "default"], timeout=8)
    best = None
    if rc == 0:
        for line in out.splitlines():
            m = re.search(r"default via (\d+\.\d+\.\d+\.\d+) dev (\S+).*?metric (\d+)", line)
            if m:
                cand = {"gw": m.group(1), "iface": m.group(2), "metric": int(m.group(3))}
                if best is None or cand["metric"] < best["metric"]:
                    best = cand
    return best


def upstream_ok():
    """True if a non-wlan default path exists (management safety for exclusive mode)."""
    dr = default_route()
    if not dr:
        return False, None
    if dr["iface"] != wifi_iface():
        ip = iface_ipv4(dr["iface"])
        return bool(ip), dr
    # default is via wifi — check other ifaces with IPv4
    rc, out, _ = run(["ip", "-4", "-o", "-brief", "addr", "show"], timeout=8)
    if rc == 0:
        for line in out.splitlines():
            parts = line.split()
            if len(parts) >= 3 and parts[1] == "UP" and parts[0] not in ("lo", wifi_iface()):
                if re.search(r"\d+\.\d+\.\d+\.\d+/", parts[2]):
                    return True, dr
    return False, dr


def internet_ok(force=False):
    now = time.time()
    if not force and now - _internet_cache["t"] < 25 and _internet_cache["ok"] is not None:
        return _internet_cache["ok"]
    # Several probe endpoints: connectivitycheck.gstatic.com is blocked in some
    # regions (Iran), so fall back to Apple/Microsoft captive endpoints. The last
    # endpoint that worked is retried first ("sticky").
    endpoints = [
        ("http://connectivitycheck.gstatic.com/generate_204", "204"),
        ("http://captive.apple.com/", "200"),
        ("http://www.msftconnecttest.com/connecttest.txt", "200"),
    ]
    sticky = _internet_cache.get("url")
    if sticky:
        endpoints.sort(key=lambda e: e[0] != sticky)
    ok = False
    for url, want in endpoints:
        rc, out, _ = run(["curl", "-s", "-m", "3", "-o", "/dev/null", "-w", "%{http_code}", url], timeout=6)
        if rc == 0 and out.strip() == want:
            ok = True
            _internet_cache.update(t=now, ok=ok, url=url)
            break
    else:
        _internet_cache.update(t=now, ok=ok)
    return ok


def saved_wifi_cons():
    """List saved 802-11-wireless connections."""
    rc, out, _ = run(["nmcli", "-t", "-f", "NAME,UUID,TYPE,DEVICE,AUTOCONNECT", "con", "show"], timeout=10)
    res = []
    if rc != 0:
        return res
    for line in out.splitlines():
        f = [unesc(x) for x in split_terse(line)]
        if len(f) >= 5 and f[2] == "802-11-wireless":
            res.append({"name": f[0], "uuid": f[1], "device": f[3] if f[3] != "--" else None,
                        "autoconnect": f[4] == "yes"})
    return res


def active_wifi_con():
    rc, out, _ = run(["nmcli", "-t", "-f", "NAME,UUID,TYPE,DEVICE,STATE", "con", "show", "--active"], timeout=10)
    if rc != 0:
        return None
    for line in out.splitlines():
        f = [unesc(x) for x in split_terse(line)]
        if len(f) >= 5 and f[2] == "802-11-wireless" and f[3] == wifi_iface():
            return {"name": f[0], "uuid": f[1], "state": f[4]}
    return None


def scan_list(rescan=False, timeout=25):
    args = ["-t", "-f", "IN-USE,SSID,CHAN,FREQ,SIGNAL,SECURITY", "dev", "wifi", "list"]
    if rescan:
        args.append("rescan")
        args.append("yes")
    rc, out, err = nmcli(args, timeout=timeout)
    if rc != 0 and rescan:  # e.g. scanning-not-allowed → fall back to cached
        rc, out, err = nmcli(["-t", "-f", "IN-USE,SSID,CHAN,FREQ,SIGNAL,SECURITY", "dev", "wifi", "list"], timeout=timeout)
    rows = []
    seen = set()
    if rc != 0:
        return rows, (err or out).strip()
    for line in out.splitlines():
        f = [unesc(x) for x in split_terse(line)]
        if len(f) < 6:
            continue
        ssid = f[1].strip()
        if not ssid:
            continue
        sec_raw = f[5].strip()
        item = {
            "ssid": ssid,
            "in_use": f[0].strip() == "*",
            "channel": int(f[2]) if f[2].isdigit() else None,
            "freq": (int(m.group(1)) if (m := re.match(r"(\d+)", f[3] or "")) else None),
            "signal": int(f[4]) if f[4].isdigit() else 0,
            "security": sec_raw or "Open",
            "open": sec_raw == "",
            "wpa3": "WPA3" in sec_raw,
            "wpa2": "WPA2" in sec_raw or "WPA1" in sec_raw or "WPA" in sec_raw,
        }
        item["quality"] = clamp(item["signal"], 0, 100)
        key = (ssid, item["channel"], item["in_use"])
        if key in seen:
            continue
        seen.add(key)
        rows.append(item)
    rows.sort(key=lambda r: (not r["in_use"], -r["signal"], r["ssid"].lower()))
    return rows, None


def hotspot_state():
    """Active hotspot info (mode, iface, channel, clients) or None."""
    rc, out, _ = run(["nmcli", "-t", "-f", "NAME,DEVICE,STATE", "con", "show", "--active"], timeout=10)
    ifname = None
    if rc == 0:
        for line in out.splitlines():
            f = [unesc(x) for x in split_terse(line)]
            if len(f) >= 3 and f[0] == HOTSPOT_CON:
                ifname = f[1]
                break
    if not ifname:
        return None
    mode = "exclusive" if ifname == wifi_iface() else "simultaneous"
    info = {"active": True, "mode": mode, "iface": ifname, "ssid": None, "channel": None,
            "freq": None, "addr": None, "clients": [], "leases": []}
    rc, out, _ = run(["iw", "dev", ifname, "info"], timeout=10)
    if rc == 0:
        for line in out.splitlines():
            s = line.strip()
            if s.lower().startswith("ssid"):
                v = s.split(":", 1)[1].strip() if ":" in s else (s.split(None, 1)[1].strip() if " " in s else "")
                info["ssid"] = unesc(v)
            elif s.startswith("channel"):
                m = re.search(r"channel (\d+) \((\d+)", s)
                if m:
                    info["channel"] = int(m.group(1))
                    info["freq"] = int(m.group(2))
    addr = iface_ipv4(ifname)
    if addr:
        info["addr"] = addr["ip"] + "/" + str(addr["prefix"])
    # Wi-Fi stations (driver-level truth)
    rc, out, _ = run(["iw", "dev", ifname, "station", "dump"], timeout=10)
    stations = []
    if rc == 0 and "Station" in out:
        cur = None
        for line in out.splitlines():
            if line.startswith("Station"):
                m = re.match(r"Station ([0-9a-f:]{17})", line.strip())
                if m:
                    cur = {"mac": m.group(1), "signal": None, "connected_time": None, "rx_rate": None}
                    stations.append(cur)
            elif cur is not None:
                s = line.strip()
                if s.startswith("signal:"):
                    m = re.search(r"(-?\d+)", s)
                    if m:
                        cur["signal"] = int(m.group(1))
                        cur["quality"] = signal_quality(cur["signal"])
                elif s.startswith("connected time:"):
                    m = re.search(r"(\d+)", s)
                    if m:
                        cur["connected_time"] = int(m.group(1))
                elif s.startswith("rx bitrate:"):
                    cur["rx_rate"] = s.split(":", 1)[1].strip()
    # DHCP leases (IP/hostname join)
    lease_map = {}
    lease_file = f"/var/lib/NetworkManager/dnsmasq-{ifname}.leases"
    try:
        with open(lease_file, encoding="utf-8") as fh:
            for line in fh:
                parts = line.split()
                if len(parts) >= 4:
                    lease_map[parts[1].lower()] = {"ip": parts[2], "hostname": parts[3] if parts[3] != "*" else ""}
    except Exception:
        pass
    info["leases"] = [{"mac": k, **v} for k, v in lease_map.items()]
    for st in stations:
        st.update(lease_map.get(st["mac"].lower(), {}))
    info["clients"] = stations
    return info


# ----------------------------------------------------------------------------- jobs

_jobs = {}
_job_lock = threading.Lock()
_job_seq = 0


def broadcast(kind, payload):
    data = json.dumps({"kind": kind, "data": payload}, ensure_ascii=False)
    with _sse_lock:
        for q in list(_sse_clients):
            try:
                q.put_nowait(data)
            except Exception:
                pass


def start_job(kind, fn, meta=None):
    global _job_seq
    with _job_lock:
        _job_seq += 1
        jid = _job_seq
        job = {"id": jid, "kind": kind, "state": "running", "message": "", "t": time.time(),
               "meta": meta or {}, "result": None}
        _jobs[jid] = job
    broadcast("job", job)
    log("job_start", kind=kind, job=jid, **{k: v for k, v in (meta or {}).items()
                                            if k not in ("password", "psk")})

    def _worker():
        try:
            res = fn()
            job.update(state="ok", message=(res or {}).get("message", ""), result=res, done_t=time.time())
            log("job_ok", kind=kind, job=jid)
        except AppError as e:
            job.update(state="error", code=e.code, message=e.message, done_t=time.time())
            log("job_error", kind=kind, job=jid, code=e.code, msg=e.message, level="error")
        except Exception as e:
            job.update(state="error", code="internal", message=f"Internal error: {e}", done_t=time.time())
            log("job_crash", kind=kind, job=jid, msg=str(e), level="error",
                trace=traceback.format_exc()[-500:])
        broadcast("job", job)
        broadcast("status", build_status(force=True))

    threading.Thread(target=_worker, daemon=True).start()
    return job


# ----------------------------------------------------------------------------- operations

def op_scan(rescan=True):
    def fn():
        rows, err = scan_list(rescan=rescan)
        if err and not rows:
            raise AppError("scan_failed", f"Scan failed: {err[:200]}")
        payload = {"rows": rows, "t": time.time(), "count": len(rows)}
        broadcast("scan", payload)
        return {"message": f"{len(rows)} networks found", "rows": rows}
    return start_job("scan", fn)


def _nm_error_map(out, err, stage):
    txt = (out + " " + err).lower()
    if "secrets were required" in txt or "no-secrets" in txt or "no secrets" in txt:
        return ("wrong_password", "Wrong password — the network rejected the connection.")
    if "not found" in txt or "ssid not found" in txt or "no network with ssid" in txt:
        return ("network_not_found", "Network not found. It may be out of range or hidden.")
    if "timeout" in txt or "timed out" in txt:
        return ("timeout", "Connection attempt timed out. The network may be out of range.")
    if "property is invalid" in txt or "psk:" in txt and "invalid" in txt:
        return ("bad_psk", "The password format was rejected (8-63 printable characters).")
    if "already exists" in txt:
        return ("exists", "A connection with this name already exists.")
    if "permission" in txt or "not authorized" in txt:
        return ("permission", "Not authorized to change network settings.")
    if "device or resource busy" in txt or "resource busy" in txt:
        return ("busy", "The wireless interface is busy — try again in a moment.")
    raw = " ".join((out + " " + err).split())[:300]
    return ("activation_failed", f"Connection failed ({stage}): {raw or 'unknown error'}")


def make_backup(tag):
    """Snapshot NM keyfiles + firewall/routing state before a mutating operation."""
    ts = time.strftime("%Y%m%d-%H%M%S")
    dest = os.path.join(BASE, "backup", "%s-%s" % (tag, ts))
    try:
        os.makedirs(dest, exist_ok=True)
        sc = "/etc/NetworkManager/system-connections"
        if os.path.isdir(sc):
            kdst = os.path.join(dest, "nm-connections")
            os.makedirs(kdst, exist_ok=True)
            for n in os.listdir(sc):
                src_f = os.path.join(sc, n)
                if os.path.isfile(src_f):
                    try:
                        shutil.copy2(src_f, kdst)
                    except OSError as e:
                        log("backup_skip_file", level="warn", file=n, msg=str(e))
        for name, argv in (("iptables.rules", ["iptables-save"]),
                           ("addr.txt", ["ip", "-4", "-o", "addr", "show"]),
                           ("routes.txt", ["ip", "route", "show"])):
            rc, out, _ = run(argv, timeout=10)
            if rc == 0 and out.strip():
                with open(os.path.join(dest, name), "w", encoding="utf-8") as fh:
                    fh.write(out)
        log("backup_created", tag=tag, path=dest)
        return dest
    except Exception as e:
        log("backup_failed", level="error", tag=tag, msg=str(e))
        return None


def op_connect(body):
    ssid = validate_ssid(body.get("ssid"))
    psk = body.get("password")
    hidden = bool(body.get("hidden"))
    open_net = bool(body.get("open")) or (psk in (None, ""))
    security_hint = body.get("security") or ""

    if open_net:
        psk_v = None
    else:
        psk_v = validate_psk(psk)

    def fn():
        make_backup("pre-connect")
        saved = {c["name"]: c for c in saved_wifi_cons()}
        existing = saved.get(ssid)
        if existing:
            if psk_v:
                # update stored secret (read old first so we can restore on failure)
                rc_s, out_s, _ = nmcli(["-t", "-s", "con", "show", existing["uuid"]], timeout=10)
                old_psk = None
                if rc_s == 0:
                    for line in out_s.splitlines():
                        if line.startswith("802-11-wireless-security.psk:"):
                            old_psk = line.split(":", 1)[1]
                nmcli(["con", "mod", existing["uuid"], "802-11-wireless-security.psk", psk_v], timeout=15)
            rc, out, err = nmcli(["-w", "40", "con", "up", existing["uuid"]], timeout=50)
            if rc != 0:
                if psk_v and old_psk is not None:
                    nmcli(["con", "mod", existing["uuid"], "802-11-wireless-security.psk", old_psk], timeout=15)
                code, msg = _nm_error_map(out, err, "activation")
                raise AppError(code, msg)
            nmcli(["con", "mod", existing["uuid"], "connection.autoconnect", "yes"], timeout=10)
            return {"message": f"Connected to {ssid}", "ssid": ssid, "mode": "existing"}

        # new connection
        keymgmt = "none"
        if not open_net:
            sec = security_hint.upper()
            if "WPA3" in sec and "WPA2" not in sec:
                keymgmt = "sae"
            else:
                keymgmt = "wpa-psk"
        args = ["con", "add", "type", "wifi", "ifname", wifi_iface(), "con-name", ssid,
                "connection.autoconnect", "no",
                "802-11-wireless.ssid", ssid]
        if hidden:
            args += ["802-11-wireless.hidden", "yes"]
        if keymgmt == "none":
            pass  # open network
        else:
            args += ["802-11-wireless-security.key-mgmt", keymgmt]
            if psk_v:
                args += ["802-11-wireless-security.psk", psk_v]
        args += ["ipv4.method", "auto"]
        rc, out, err = nmcli(args, timeout=20)
        if rc != 0:
            code, msg = _nm_error_map(out, err, "create")
            raise AppError(code, msg)
        rc, out, err = nmcli(["-w", "40", "con", "up", ssid], timeout=50)
        if rc != 0:
            code, msg = _nm_error_map(out, err, "activation")
            # remove the half-created profile so no zombie autoconnect lingers
            nmcli(["con", "delete", ssid], timeout=10)
            raise AppError(code, msg)
        nmcli(["con", "mod", ssid, "connection.autoconnect", "yes"], timeout=10)
        return {"message": f"Connected to {ssid}", "ssid": ssid, "mode": "new"}

    return start_job("connect", fn, meta={"ssid": ssid, "hidden": hidden, "open": open_net})


def op_disconnect():
    def fn():
        aw = active_wifi_con()
        if not aw:
            raise AppError("not_connected", "Wi-Fi is not connected.")
        # disable autoconnect first so NM does not immediately re-activate
        nmcli(["con", "mod", aw["uuid"], "connection.autoconnect", "no"], timeout=10)
        rc, out, err = nmcli(["-w", "20", "con", "down", aw["uuid"]], timeout=25)
        if rc != 0:
            raise AppError("disconnect_failed", f"Disconnect failed: {(out+err).strip()[:200]}")
        return {"message": f"Disconnected from {aw['name']} (autoconnect off)", "name": aw["name"]}
    return start_job("disconnect", fn)


def op_reconnect(body):
    name = body.get("name")

    def fn():
        saved = {c["name"]: c for c in saved_wifi_cons()}
        if name:
            target = saved.get(name)
        else:
            aw = active_wifi_con()
            target = saved.get(aw["name"]) if aw else None
            if not target:
                # pick the most recently used = any saved with device set? fallback first
                if not saved:
                    raise AppError("no_saved", "No saved networks to reconnect to.")
                target = list(saved.values())[0]
        if not target:
            raise AppError("unknown_network", "Unknown saved network.")
        nmcli(["con", "mod", target["uuid"], "connection.autoconnect", "yes"], timeout=10)
        rc, out, err = nmcli(["-w", "40", "con", "up", target["uuid"]], timeout=50)
        if rc != 0:
            code, msg = _nm_error_map(out, err, "reconnect")
            raise AppError(code, msg)
        return {"message": f"Connected to {target['name']}", "name": target["name"]}
    return start_job("reconnect", fn, meta={"name": name})


def op_forget(body):
    name = body.get("name")

    def fn():
        wifi_names = [c["name"] for c in saved_wifi_cons()]
        validate_con_name(name, wifi_names)
        target = next(c for c in saved_wifi_cons() if c["name"] == name)
        # safety: never touch non-wi-fi or the hotspot profile here
        if name == HOTSPOT_CON:
            raise AppError("protected", "Use the hotspot controls instead.")
        aw = active_wifi_con()
        if aw and aw["uuid"] == target["uuid"]:
            rc, out, err = nmcli(["-w", "20", "con", "down", target["uuid"]], timeout=25)
            if rc != 0:
                raise AppError("forget_failed", f"Could not deactivate: {(out+err).strip()[:200]}")
        rc, out, err = nmcli(["con", "delete", target["uuid"]], timeout=15)
        if rc != 0:
            raise AppError("forget_failed", f"Forget failed: {(out+err).strip()[:200]}")
        return {"message": f"Forgot “{name}”", "name": name}
    return start_job("forget", fn, meta={"name": name})


def _ensure_ap_if():
    """Create the ap0 virtual AP interface on the same phy. Returns iface name or None."""
    global _mode
    ap = "ap0"
    rc, out, _ = run(["iw", "dev"], timeout=8)
    exists = bool(rc == 0 and re.search(rf"Interface {ap}\b", out))
    if exists:
        # reuse if it's already AP-typed, else recreate
        rc2, out2, _ = run(["iw", "dev", ap, "info"], timeout=8)
        if rc2 == 0 and "type AP" in out2:
            return ap
        run(["iw", "dev", ap, "del"], timeout=8)
        exists = False
    phy = phy_name(wifi_iface())
    rc, out, err = run(["iw", "phy", phy, "interface", "add", ap, "type", "__ap"], timeout=10)
    if rc != 0:
        log("ap_if_failed", level="error", err=(err or out).strip()[:200])
        return None
    run(["ip", "link", "set", ap, "up"], timeout=8)
    time.sleep(0.5)
    return ap


def _delete_ap_if():
    run(["iw", "dev", "ap0", "del"], timeout=8)


def op_hotspot_start(body):
    ssid = validate_ssid(body.get("ssid") or "ZimaOS Hotspot")
    psk = validate_psk(body.get("password"))
    channel = validate_channel(body.get("channel"))
    subnet = validate_subnet(body.get("subnet"))
    security = validate_security(body.get("security"))
    autostart = bool(body.get("autostart"))

    def fn():
        global _mode
        make_backup("pre-hotspot-start")
        caps = get_caps()
        link = wlan_link()
        up_ok, up_info = upstream_ok()
        notes = []

        ifname = _ensure_ap_if()
        mode = "simultaneous"
        if not ifname:
            if not up_ok:
                raise AppError("no_upstream",
                               "Cannot start hotspot: the AP interface could not be created and "
                               "there is no wired upstream to fall back on (would lose dashboard access).",
                               http=409)
            mode = "exclusive"
            ifname = wifi_iface()
            notes.append("Simultaneous mode unavailable — switched to exclusive mode "
                         "(Wi-Fi client disconnected while the hotspot runs).")

        # pin channel: with a live client link, single-channel radio forces AP = client channel
        eff_channel = channel or 6
        if mode == "simultaneous" and link.get("connected") and link.get("channel"):
            if channel and channel != link["channel"]:
                notes.append(f"Channel adjusted {channel} -> {link['channel']} to match the "
                             f"active Wi-Fi client link (single shared radio channel).")
            eff_channel = link["channel"]

        # clean leftover profile
        rc, out, _ = run(["nmcli", "-t", "-f", "NAME", "con", "show"], timeout=10)
        if rc == 0 and any(unesc(split_terse(l)[0]) == HOTSPOT_CON for l in out.splitlines() if l):
            nmcli(["con", "delete", HOTSPOT_CON], timeout=15)

        args = ["con", "add", "type", "wifi", "ifname", ifname, "con-name", HOTSPOT_CON,
                "connection.autoconnect", "no",
                "802-11-wireless.ssid", ssid,
                "802-11-wireless.mode", "ap",
                "802-11-wireless.band", "bg",
                "802-11-wireless.channel", str(eff_channel),
                "802-11-wireless.cloned-mac-address", "random",
                "802-11-wireless-security.key-mgmt", security,
                "802-11-wireless-security.psk", psk,
                "ipv4.method", "shared",
                "ipv4.addresses", subnet]
        rc, out, err = nmcli(args, timeout=20)
        if rc != 0:
            if mode == "simultaneous":
                _cleanup_hotspot(iface_delete=True)
                if up_ok:
                    notes.append("AP virtual interface path failed — falling back to exclusive mode "
                                 "(Wi-Fi client disconnects while hotspot runs).")
                    mode, ifname = "exclusive", wifi_iface()
                    args = [a if a != "ap0" else ifname for a in args]
                    args[args.index("ifname") + 1] = ifname
                    rc, out, err = nmcli(args, timeout=20)
            if rc != 0:
                _cleanup_hotspot(iface_delete=True)
                code, msg = _nm_error_map(out, err, "hotspot-create")
                raise AppError(code, msg)

        rc, out, err = nmcli(["-w", "30", "con", "up", HOTSPOT_CON], timeout=40)
        if rc != 0:
            _cleanup_hotspot(iface_delete=(mode == "simultaneous"))
            if mode == "simultaneous" and up_ok:
                # last resort: exclusive mode
                notes.append("AP activation failed — falling back to exclusive mode "
                             "(Wi-Fi client disconnects while hotspot runs).")
                mode, ifname = "exclusive", wifi_iface()
                rc2, out2, err2 = run(["nmcli", "-t", "-f", "NAME", "con", "show"], timeout=10)
                # recreate con bound to wlan0
                nmcli(["con", "delete", HOTSPOT_CON], timeout=10)
                args[args.index("ifname") + 1] = ifname
                nmcli(args, timeout=20)
                rc, out, err = nmcli(["-w", "30", "con", "up", HOTSPOT_CON], timeout=40)
                if rc != 0:
                    _cleanup_hotspot(iface_delete=False)
                    code, msg = _nm_error_map(out, err, "hotspot-up")
                    raise AppError(code, msg)
            else:
                code, msg = _nm_error_map(out, err, "hotspot-up")
                raise AppError(code, msg)

        time.sleep(1.0)
        st = hotspot_state()
        if not st:
            _cleanup_hotspot(iface_delete=(mode == "simultaneous"))
            raise AppError("hotspot_verify", "Hotspot activation could not be verified.", http=500)

        _mode = mode
        _save_cfg({"hotspot": {"ssid": ssid, "password": psk, "channel": channel,
                               "subnet": subnet, "security": security, "autostart": autostart}})
        log("hotspot_started", mode=mode, ssid=ssid, channel=eff_channel, subnet=subnet)
        msg = f"Hotspot “{ssid}” started ({'dual STA+AP' if mode == 'simultaneous' else 'exclusive'} mode)"
        broadcast("hotspot", {"active": True, "mode": mode, "ssid": ssid, "notes": notes})
        return {"message": msg, "mode": mode, "notes": notes, "channel": eff_channel,
                "iface": st["iface"], "addr": st.get("addr")}

    return start_job("hotspot_start", fn, meta={"ssid": ssid, "channel": channel, "mode_hint": "auto"})


def _cleanup_hotspot(iface_delete=True):
    nmcli(["-w", "15", "con", "down", HOTSPOT_CON], timeout=20)
    nmcli(["con", "delete", HOTSPOT_CON], timeout=15)
    if iface_delete:
        _delete_ap_if()


def op_hotspot_stop():
    def fn():
        global _mode
        make_backup("pre-hotspot-stop")
        st = hotspot_state()
        mode = st["iface"] if False else (st or {}).get("mode")
        rc, out, err = nmcli(["-w", "15", "con", "down", HOTSPOT_CON], timeout=20)
        nmcli(["con", "delete", HOTSPOT_CON], timeout=15)
        if mode == "simultaneous" or (mode is None):
            _delete_ap_if()
        _mode = None
        _save_cfg({"hotspot": {"autostart": False}})
        log("hotspot_stopped", mode=mode)
        broadcast("hotspot", {"active": False})
        return {"message": "Hotspot stopped. Saved Wi-Fi networks reconnect automatically."}
    return start_job("hotspot_stop", fn)


def op_update_settings(body):
    """Persist hotspot defaults without starting anything."""
    updates = {}
    if "ssid" in body:
        updates["ssid"] = validate_ssid(body.get("ssid"))
    if "password" in body:
        updates["password"] = validate_psk(body.get("password"))
    if "channel" in body:
        updates["channel"] = validate_channel(body.get("channel"))
    if "subnet" in body:
        updates["subnet"] = validate_subnet(body.get("subnet"))
    if "security" in body:
        updates["security"] = validate_security(body.get("security"))
    if "autostart" in body:
        updates["autostart"] = bool(body.get("autostart"))
    if updates:
        _save_cfg({"hotspot": updates})
    return updates


# ----------------------------------------------------------------------------- config/state

_cfg_lock = threading.Lock()


def _load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _save_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)
    try:
        os.chmod(path, 0o600)
    except Exception:
        pass


def _save_cfg(partial):
    with _cfg_lock:
        cfg = _load_json(CFG_PATH, {})
        for k, v in partial.items():
            if isinstance(v, dict) and isinstance(cfg.get(k), dict):
                cfg[k].update(v)
            else:
                cfg[k] = v
        _save_json(CFG_PATH, cfg)
    return cfg


def get_cfg():
    return _load_json(CFG_PATH, {})


# ----------------------------------------------------------------------------- status

def build_status(force=False):
    now = time.time()
    with _sys_lock:
        if not force and _status_cache["data"] and now - _status_cache["t"] < 1.0:
            return _status_cache["data"]
        try:
            data = _build_status_locked()
        except Exception as e:
            log("status_error", level="error", msg=str(e))
            data = {"error": str(e)}
        _status_cache.update(t=now, data=data)
        return data


def _build_status_locked():
    now = time.time()
    iface = wifi_iface()
    caps = get_caps()
    link = wlan_link()
    addr = iface_ipv4(iface)
    dr = default_route()
    up_ok, _ = upstream_ok()
    aw = active_wifi_con()
    hot = hotspot_state()
    saved = saved_wifi_cons()

    # eth0 (management) summary
    mgmt = {"iface": None, "ip": None, "gw": None}
    rc, out, _ = run(["ip", "-4", "-o", "-brief", "addr", "show"], timeout=8)
    if rc == 0:
        for line in out.splitlines():
            parts = line.split()
            if len(parts) >= 3 and parts[0] in ("eth0", "enp3s0", "enp1s0") and parts[1] == "UP":
                m = re.search(r"(\d+\.\d+\.\d+\.\d+)", parts[2])
                if m:
                    mgmt.update(iface=parts[0], ip=m.group(1))
                    break
    if dr:
        mgmt["gw"] = dr.get("iface")

    # dns
    dns = []
    try:
        with open("/etc/resolv.conf", encoding="utf-8") as f:
            for line in f:
                if line.startswith("nameserver"):
                    v = line.split()[1]
                    if v not in dns and v != "::":
                        dns.append(v)
    except Exception:
        pass

    state = "disconnected"
    if hot and hot.get("active"):
        state = "hotspot" if not link.get("connected") else "client+hotspot"
    elif link.get("connected"):
        state = "connected"

    data = {
        "version": VERSION,
        "time": now,
        "state": state,
        "wifi": {
            "iface": iface,
            "driver": caps.get("driver"),
            "mac": _iface_mac(iface),
            "connected": link.get("connected"),
            "ssid": link.get("ssid"),
            "bssid": link.get("bssid"),
            "signal": link.get("signal"),
            "quality": link.get("quality"),
            "freq": link.get("freq"),
            "channel": link.get("channel"),
            "band": link.get("band"),
            "rx_rate": link.get("rx_rate"),
            "tx_rate": link.get("tx_rate"),
            "ip": addr["ip"] if addr else None,
            "prefix": addr["prefix"] if addr else None,
            "active_con": aw["name"] if aw else None,
            "autoconnect": next((c["autoconnect"] for c in saved if aw and c["name"] == aw["name"]), None),
        },
        "hotspot": hot or {"active": False},
        "upstream": {
            "default_iface": dr["iface"] if dr else None,
            "default_gw": dr["gw"] if dr else None,
            "metric": dr["metric"] if dr else None,
            "mgmt_ip": mgmt["ip"],
            "mgmt_iface": mgmt["iface"],
            "ok": up_ok,
        },
        "internet": internet_ok(),
        "dns": dns[:4],
        "saved": saved,
        "caps": caps,
        "hotspot_cfg": _redact_cfg(get_cfg().get("hotspot", {})),
        "events": list(_events)[-14:][::-1],
    }
    return data


def _iface_mac(iface):
    try:
        with open(f"/sys/class/net/{iface}/address", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return None


def _redact_cfg(hs):
    if not hs:
        return {}
    out = dict(hs)
    if out.get("password"):
        out["has_password"] = True
        out.pop("password", None)
    return out


# ----------------------------------------------------------------------------- auth

_auth_lock = threading.Lock()


def _load_auth():
    a = _load_json(AUTH_PATH, None)
    if not a:
        with _auth_lock:
            a = _load_json(AUTH_PATH, None)
            if not a:
                salt = secrets.token_hex(16)
                # Password precedence: WM_ADMIN_PASSWORD env (set by install.sh) →
                # first-boot generated random → legacy fallback. Never a guessable
                # hardcoded default: this service controls the host's networking.
                pw = (os.environ.get("WM_ADMIN_PASSWORD", "").strip()
                      or os.environ.get("WM_PASSWORD", "").strip())
                generated = False
                if not pw:
                    pw = secrets.token_urlsafe(12)
                    generated = True
                a = {"user": os.environ.get("WM_ADMIN_USER", "admin").strip() or "admin",
                     "salt": salt,
                     "hash": hashlib.sha256((salt + pw).encode()).hexdigest()}
                _save_json(AUTH_PATH, a)
                if generated:
                    # One-time reveal so the installer can print it to the console.
                    # Written to the data dir (0600) — never to the event log.
                    try:
                        pwfile = os.path.join(BASE, "initial-password.txt")
                        with open(pwfile, "w", encoding="utf-8") as f:
                            f.write("user: %s\npassword: %s\n" % (a["user"], pw))
                        os.chmod(pwfile, 0o600)
                    except Exception:
                        pass
                    log("auth_default_created", user=a["user"], generated=True)
                else:
                    log("auth_default_created", user=a["user"], generated=False)
    return a


_auth_fail = {}
_auth_lock2 = threading.Lock()


def check_auth(header):
    if not header or not header.lower().startswith("basic "):
        return False, "missing"
    try:
        raw = base64.b64decode(header.split(" ", 1)[1]).decode("utf-8")
        user, _, pw = raw.partition(":")
    except Exception:
        return False, "malformed"
    ip = "local"
    now = time.time()
    with _auth_lock2:
        fails = _auth_fail.get(ip, [0, 0])
        if fails[0] >= 12 and now - fails[1] < 300:
            return False, "locked"
    a = _load_auth()
    ok = hmac.compare_digest(user, a.get("user", "")) and \
        hmac.compare_digest(hashlib.sha256((a.get("salt", "") + pw).encode()).hexdigest(),
                            a.get("hash", ""))
    if not ok:
        with _auth_lock2:
            fails = _auth_fail.get(ip, [0, 0])
            fails[0] += 1
            fails[1] = now
            _auth_fail[ip] = fails
        return False, "bad_credentials"
    with _auth_lock2:
        _auth_fail.pop(ip, None)
    return True, ""


def op_change_password(body):
    a = _load_auth()
    cur = body.get("current") or ""
    new = body.get("new") or ""
    if not hmac.compare_digest(hashlib.sha256((a.get("salt", "") + cur).encode()).hexdigest(),
                               a.get("hash", "")):
        raise AppError("bad_current", "Current password is incorrect.", http=401)
    if not (6 <= len(new) <= 64) or any(ord(c) < 0x20 or ord(c) > 0x7E for c in new):
        raise AppError("bad_new", "New password must be 6-64 printable characters.")
    salt = secrets.token_hex(16)
    a.update(salt=salt, hash=hashlib.sha256((salt + new).encode()).hexdigest())
    _save_json(AUTH_PATH, a)
    log("password_changed")
    return {"message": "Password updated."}


# ----------------------------------------------------------------------------- SSE

_sse_clients = set()
_sse_lock = threading.Lock()


# ----------------------------------------------------------------------------- HTTP

class Handler(BaseHTTPRequestHandler):
    server_version = "WifiManager/1.0"
    protocol_version = "HTTP/1.1"

    # ---------------- plumbing
    def log_message(self, fmt, *args):  # quiet default access log
        pass

    def _send(self, code, body, ctype="application/json; charset=utf-8", extra=None):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False).encode("utf-8")
        elif isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        if extra:
            for k, v in extra.items():
                self.send_header(k, v)
        self.end_headers()
        try:
            self.wfile.write(body)
        except Exception:
            pass

    def _err(self, code, err_code, msg):
        self._send(code, {"error": {"code": err_code, "message": msg}})

    def _authed(self):
        ok, why = check_auth(self.headers.get("Authorization"))
        if not ok:
            if why == "locked":
                self._send(429, {"error": {"code": "locked", "message": "Too many failed attempts — try again later."}})
            else:
                self._send(401, {"error": {"code": "unauthorized", "message": "Authentication required."}},
                           extra={"WWW-Authenticate": 'Basic realm="ZimaOS Wi-Fi Manager", charset="UTF-8"'})
            return False
        return True

    def _body(self):
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            n = 0
        if n <= 0:
            return {}
        if n > MAX_BODY:
            raise AppError("too_large", "Request body too large.")
        raw = self.rfile.read(n)
        try:
            obj = json.loads(raw.decode("utf-8"))
        except Exception:
            raise AppError("bad_json", "Invalid JSON body.")
        if not isinstance(obj, dict):
            raise AppError("bad_json", "JSON object expected.")
        return obj

    # ---------------- GET
    def do_GET(self):
        try:
            u = urlparse(self.path)
            path = u.path
            if path == "/icon.svg":
                return self._static("icon.svg", public=True)
            if path == "/api/ping":
                return self._send(200, {"ok": True, "version": VERSION})
            if not self._authed():
                return
            if path in ("/", "/index.html"):
                return self._static("index.html")
            if path.startswith("/api/"):
                if path == "/api/status":
                    return self._send(200, build_status())
                if path == "/api/events":
                    return self._sse()
                if path == "/api/log":
                    return self._send(200, {"events": list(_events)[-80:][::-1]})
                if path == "/api/diag":
                    return self._send(200, self._diag())
                if path.startswith("/api/jobs/"):
                    try:
                        jid = int(path.rsplit("/", 1)[1])
                    except ValueError:
                        return self._err(400, "validation", "Bad job id.")
                    job = _jobs.get(jid)
                    if not job:
                        return self._err(404, "not_found", "No such job.")
                    j = dict(job)
                    if isinstance(j.get("meta"), dict):
                        j["meta"] = {k: v for k, v in j["meta"].items()
                                     if k not in ("password", "psk")}
                    return self._send(200, j)
                return self._err(404, "not_found", "Unknown API endpoint.")
            # static assets
            name = path.lstrip("/")
            if name in ("app.js", "style.css", "favicon.ico"):
                return self._static(name)
            return self._err(404, "not_found", "Not found.")
        except AppError as e:
            self._err(e.http, e.code, e.message)
        except Exception as e:
            log("http_get_error", level="error", msg=str(e))
            self._err(500, "internal", "Internal server error.")

    # ---------------- POST
    def do_POST(self):
        try:
            u = urlparse(self.path)
            path = u.path
            if not self._authed():
                return
            body = self._body()
            if path == "/api/scan":
                job = op_scan(rescan=bool(body.get("rescan", True)))
                return self._send(202, {"job": job})
            if path == "/api/connect":
                job = op_connect(body)
                return self._send(202, {"job": job})
            if path == "/api/disconnect":
                return self._send(202, {"job": op_disconnect()})
            if path == "/api/reconnect":
                return self._send(202, {"job": op_reconnect(body)})
            if path == "/api/forget":
                return self._send(202, {"job": op_forget(body)})
            if path == "/api/hotspot/start":
                return self._send(202, {"job": op_hotspot_start(body)})
            if path == "/api/hotspot/stop":
                return self._send(202, {"job": op_hotspot_stop()})
            if path == "/api/settings/hotspot":
                return self._send(200, {"saved": op_update_settings(body)})
            if path == "/api/settings/password":
                return self._send(200, op_change_password(body))
            return self._err(404, "not_found", "Unknown API endpoint.")
        except AppError as e:
            self._err(e.http, e.code, e.message)
        except Exception as e:
            log("http_post_error", level="error", msg=str(e),
                trace=traceback.format_exc()[-400:])
            self._err(500, "internal", "Internal server error.")

    # ---------------- static
    def _static(self, name, public=False):
        if not public and not self._authed():
            return
        base = os.path.realpath(WEB)
        full = os.path.realpath(os.path.join(base, name))
        if not full.startswith(base + os.sep) or not os.path.isfile(full):
            return self._err(404, "not_found", "Not found.")
        ctype = {"html": "text/html; charset=utf-8",
                 "js": "application/javascript; charset=utf-8",
                 "css": "text/css; charset=utf-8",
                 "svg": "image/svg+xml"}.get(name.rsplit(".", 1)[-1], "application/octet-stream")
        with open(full, "rb") as f:
            data = f.read()
        self._send(200, data, ctype=ctype)

    # ---------------- SSE
    def _sse(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "keep-alive")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()
        q = Queue(maxsize=200)
        with _sse_lock:
            _sse_clients.add(q)
        try:
            self.wfile.write(b"event: hello\ndata: {\"ok\":true}\n\n")
            self.wfile.flush()
        except Exception:
            pass
        last = time.time()
        try:
            while True:
                try:
                    msg = q.get(timeout=15)
                    self.wfile.write(msg.encode("utf-8") + b"\n\n")
                except Empty:
                    if time.time() - last > 600:
                        break
                    self.wfile.write(b": ping\n\n")
                try:
                    self.wfile.flush()
                except Exception:
                    break
                last = time.time()
        finally:
            with _sse_lock:
                _sse_clients.discard(q)

    # ---------------- diag
    def _diag(self):
        d = {}
        rc, out, _ = run(["nmcli", "-t", "-f", "GENERAL.STATE,GENERAL.DEVICE", "dev"], timeout=8)
        d["devices"] = out.strip().splitlines() if rc == 0 else []
        rc, out, _ = run(["ip", "-4", "-o", "-brief", "addr", "show"], timeout=8)
        d["addresses"] = out.strip().splitlines() if rc == 0 else []
        rc, out, _ = run(["ip", "route", "show"], timeout=8)
        d["routes"] = out.strip().splitlines() if rc == 0 else []
        rc, out, _ = run(["nmcli", "-v"], timeout=8)
        d["networkmanager"] = out.strip() or "unknown"
        d["self"] = "wifi-manager %s (pid %d)" % (VERSION, os.getpid())
        d["hotspot_active"] = bool(hotspot_state())
        d["internet"] = internet_ok(force=True)
        d["backups"] = sorted(os.listdir(os.path.join(BASE, "backup"))) if os.path.isdir(os.path.join(BASE, "backup")) else []
        d["caps"] = get_caps()
        d["log_tail"] = list(_events)[-30:][::-1]
        d["rollback"] = ("Backups: /DATA/wifi-manager/backup/ (NM keyfiles + iptables). "
                         "Restore: cp keyfiles back to /etc/NetworkManager/system-connections/ then "
                         "systemctl restart NetworkManager — or run /DATA/wifi-manager/rollback.sh")
        return d


# ----------------------------------------------------------------------------- startup

def restore_hotspot_if_configured():
    cfg = get_cfg().get("hotspot", {})
    if cfg.get("autostart") and cfg.get("ssid") and cfg.get("password"):
        log("hotspot_autostart", ssid=cfg.get("ssid"))
        body = {"ssid": cfg["ssid"], "password": cfg["password"],
                "channel": cfg.get("channel"), "subnet": cfg.get("subnet"),
                "security": cfg.get("security"), "autostart": True}
        try:
            op_hotspot_start(body)
        except AppError as e:
            log("hotspot_autostart_failed", level="error", code=e.code, msg=e.message)


def main():
    try:
        os.makedirs(WEB, exist_ok=True)
    except OSError:
        pass
    os.makedirs(os.path.join(BASE, "logs"), exist_ok=True)
    _load_auth()
    iface = wifi_iface()
    caps = get_caps()
    log("backend_start", version=VERSION, iface=iface,
        phy=caps.get("phy"), driver=caps.get("driver"),
        simultaneous=caps.get("simultaneous"), bands=caps.get("band"))
    # note: ap0 leftover from a crash?
    rc, out, _ = run(["iw", "dev"], timeout=8)
    if rc == 0 and re.search(r"\bInterface ap0\b", out) and not hotspot_state():
        log("cleanup_stale_ap0")
        _delete_ap_if()
    threading.Thread(target=restore_hotspot_if_configured, daemon=True).start()
    srv = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    srv.daemon_threads = True
    log("listening", port=PORT)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
