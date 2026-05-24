#!/usr/bin/env python3
"""Pi Monitor agent — exposes live system metrics as JSON over HTTP.

Runs as a systemd service on the Raspberry Pi and is polled by the desktop
Electron widget. Deliberately stdlib-only for the HTTP layer (no FastAPI/uvicorn)
so it stays independent of the Haven container's venv and keeps working even if
Haven is down. The only third-party dependency is psutil (apt install python3-psutil).

Endpoints:
  GET /metrics   -> full metrics snapshot (also served at /)
  GET /healthz   -> {"ok": true} liveness probe (no auth)

Env vars:
  MONITOR_PORT   listen port (default 8080)
  MONITOR_TOKEN  optional shared secret; if set, /metrics requires it via
                 ?token=... or the X-Monitor-Token header.
"""
import json
import os
import platform
import socket
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

try:
    import psutil
except ImportError:  # pragma: no cover - surfaced to the client as ok:false
    psutil = None

PORT = int(os.environ.get("MONITOR_PORT", "8080"))
TOKEN = os.environ.get("MONITOR_TOKEN", "")
BOOT_TIME = psutil.boot_time() if psutil else time.time()

collector = None  # set in __main__, referenced by the request handler at runtime


def read_cpu_temp():
    """Best-effort CPU temperature in °C. Tries psutil, sysfs, then vcgencmd."""
    if psutil and hasattr(psutil, "sensors_temperatures"):
        try:
            temps = psutil.sensors_temperatures()
            for key in ("cpu_thermal", "coretemp", "cpu-thermal", "soc_thermal"):
                if temps.get(key):
                    return round(temps[key][0].current, 1)
            for entries in temps.values():
                if entries:
                    return round(entries[0].current, 1)
        except Exception:
            pass
    try:
        with open("/sys/class/thermal/thermal_zone0/temp") as f:
            return round(int(f.read().strip()) / 1000.0, 1)
    except Exception:
        pass
    try:
        out = subprocess.check_output(["vcgencmd", "measure_temp"], text=True, timeout=2)
        return round(float(out.split("=")[1].split("'")[0]), 1)  # temp=45.6'C
    except Exception:
        pass
    return None


def read_throttled():
    """Raspberry Pi throttling / under-voltage flags via vcgencmd (best effort)."""
    try:
        out = subprocess.check_output(["vcgencmd", "get_throttled"], text=True, timeout=2)
        val = int(out.strip().split("=")[1], 16)
        return {
            "raw": hex(val),
            "under_voltage_now": bool(val & 0x1),
            "freq_capped_now": bool(val & 0x2),
            "throttled_now": bool(val & 0x4),
            "under_voltage_occurred": bool(val & 0x10000),
            "throttled_occurred": bool(val & 0x40000),
        }
    except Exception:
        return None


def collect(prev_net):
    """Build one metrics snapshot. prev_net is a mutable dict for rate calc."""
    now = time.time()
    data = {
        "ok": True,
        "timestamp": now,
        "host": {
            "hostname": socket.gethostname(),
            "platform": platform.platform(),
            "machine": platform.machine(),
            "python": platform.python_version(),
            "uptime_seconds": now - BOOT_TIME,
            "boot_time": BOOT_TIME,
        },
    }
    if not psutil:
        data["ok"] = False
        data["error"] = "psutil not installed (sudo apt install python3-psutil)"
        return data

    # --- CPU ---
    try:
        load1, load5, load15 = os.getloadavg()
    except (OSError, AttributeError):
        load1 = load5 = load15 = None
    freq = psutil.cpu_freq()
    data["cpu"] = {
        "percent": psutil.cpu_percent(interval=None),
        "per_core": psutil.cpu_percent(interval=None, percpu=True),
        "cores_logical": psutil.cpu_count(logical=True),
        "cores_physical": psutil.cpu_count(logical=False),
        "load_avg": [load1, load5, load15],
        "freq_mhz": round(freq.current) if freq else None,
        "freq_max_mhz": round(freq.max) if freq and freq.max else None,
    }

    # --- Memory ---
    vm = psutil.virtual_memory()
    sm = psutil.swap_memory()
    data["memory"] = {
        "total": vm.total, "used": vm.used,
        "available": vm.available, "percent": vm.percent,
    }
    data["swap"] = {"total": sm.total, "used": sm.used, "percent": sm.percent}

    # --- Disks ---
    disks = []
    for part in psutil.disk_partitions(all=False):
        if part.fstype in ("squashfs", "tmpfs", "devtmpfs", "overlay", "", "ramfs"):
            continue
        try:
            u = psutil.disk_usage(part.mountpoint)
        except (PermissionError, OSError):
            continue
        disks.append({
            "mount": part.mountpoint, "device": part.device, "fstype": part.fstype,
            "total": u.total, "used": u.used, "free": u.free, "percent": u.percent,
        })
    data["disks"] = disks

    # --- Network throughput ---
    net = psutil.net_io_counters()
    sent_bps = recv_bps = None
    if prev_net["t"] is not None:
        dt = now - prev_net["t"]
        if dt > 0:
            sent_bps = max(0, (net.bytes_sent - prev_net["sent"]) / dt)
            recv_bps = max(0, (net.bytes_recv - prev_net["recv"]) / dt)
    prev_net.update({"t": now, "sent": net.bytes_sent, "recv": net.bytes_recv})
    data["network"] = {
        "bytes_sent": net.bytes_sent, "bytes_recv": net.bytes_recv,
        "sent_bps": sent_bps, "recv_bps": recv_bps,
    }

    # --- Temp + Pi throttle (best effort) ---
    data["temp_c"] = read_cpu_temp()
    throttled = read_throttled()
    if throttled:
        data["throttle"] = throttled

    data["processes"] = len(psutil.pids())
    return data


class Collector(threading.Thread):
    """Samples metrics on a fixed cadence so HTTP requests just read the cache.

    Decoupling sampling from request timing keeps CPU% windows consistent and
    lets multiple clients (widget + browser) poll without skewing readings.
    """

    def __init__(self, interval=1.0):
        super().__init__(daemon=True)
        self.interval = interval
        self.latest = {"ok": False, "error": "starting", "timestamp": time.time()}
        self._prev_net = {"t": None, "sent": 0, "recv": 0}
        if psutil:  # prime the cpu_percent deltas so the first sample is real
            psutil.cpu_percent(interval=None)
            psutil.cpu_percent(interval=None, percpu=True)

    def run(self):
        while True:
            try:
                self.latest = collect(self._prev_net)
            except Exception as exc:  # never let the loop die
                self.latest = {"ok": False, "error": str(exc), "timestamp": time.time()}
            time.sleep(self.interval)


class Handler(BaseHTTPRequestHandler):
    server_version = "PiMonitor/1.0"

    def _auth_ok(self):
        if not TOKEN:
            return True
        if self.headers.get("X-Monitor-Token") == TOKEN:
            return True
        params = parse_qs(urlparse(self.path).query)
        return params.get("token", [None])[0] == TOKEN

    def _send(self, code, payload):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        if path in ("/healthz", "/health"):
            self._send(200, {"ok": True})
            return
        if not self._auth_ok():
            self._send(401, {"ok": False, "error": "unauthorized"})
            return
        if path in ("/", "/metrics"):
            self._send(200, collector.latest)
            return
        self._send(404, {"ok": False, "error": "not found"})

    def log_message(self, *args):  # silence per-request stderr noise
        pass


def main():
    global collector
    collector = Collector(interval=1.0)
    collector.start()
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"Pi Monitor listening on :{PORT} (token={'set' if TOKEN else 'none'})", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
