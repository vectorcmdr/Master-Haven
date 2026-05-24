# Pi Monitor

A lightweight monitoring system for the Haven Raspberry Pi (`10.0.0.229`):

- **`pi-agent/`** — a standalone Python + `psutil` service that runs on the Pi (via systemd) and exposes live system metrics as JSON at `http://<pi>:8080/metrics`. Stdlib-only HTTP layer, so it stays up even if the Haven Docker container is down.
- **`electron-app/`** — a desktop widget for this PC. Polls the Pi every 2s and shows CPU, RAM, temperature, storage, and network with rolling sparklines for CPU / RAM / temp.

```
┌──────────────┐    HTTP poll /metrics     ┌────────────────────┐
│  Pi 5         │  ◀──────────────────────  │  Windows PC        │
│  pi_monitor   │  ──────────────────────▶  │  Electron widget   │
│  :8080 (json) │      JSON snapshot         │  (sparklines)      │
└──────────────┘                            └────────────────────┘
```

---

## 1. Install the agent on the Pi

Copy the `pi-agent/` folder to the Pi and run the installer:

```bash
# from your PC
scp -r Pi-Monitor/pi-agent pi8gb@10.0.0.229:~/pi-monitor-agent

# then on the Pi
ssh pi8gb@10.0.0.229
cd ~/pi-monitor-agent
chmod +x install.sh
./install.sh
```

The installer:
1. Installs `python3-psutil` (apt) if missing.
2. Copies the agent to `/opt/pi-monitor/`.
3. Writes and enables a `pi-monitor.service` systemd unit (auto-starts on boot, restarts on crash).

Verify:

```bash
sudo systemctl status pi-monitor
curl http://localhost:8080/metrics
journalctl -u pi-monitor -f      # live logs
```

**Options:**
- Custom port: `MONITOR_PORT=9000 ./install.sh`
- Require a shared secret: `MONITOR_TOKEN=somesecret ./install.sh` (then set the same token in the widget settings).

**Firewall:** the agent listens on `0.0.0.0:8080`. On the LAN that's reachable directly. The temperature read uses `psutil` → `/sys/class/thermal` → `vcgencmd` in that order, so it works without special permissions.

---

## 2. Run the widget on this PC

Requires [Node.js](https://nodejs.org) (LTS) installed.

```powershell
cd Pi-Monitor\electron-app
npm install
npm start
```

On first launch it polls `10.0.0.229:8080` (the default). Click the **⚙ gear** to change:
- **Host / IP** — the Pi's LAN IP (`10.0.0.229`), or its **Tailscale IP** when you're away from home.
- **Port** — match the agent's `MONITOR_PORT`.
- **Poll interval** — default 2000 ms.
- **Token** — only if you set `MONITOR_TOKEN` on the agent.
- **Always on top** — keeps the widget floating above other windows.

Settings persist to Electron's `userData/config.json`.

> **Remote access:** the widget fetches over plain HTTP, which is fine on the LAN or over Tailscale's encrypted mesh. Don't expose port 8080 to the public internet — if you ever need that, put it behind the existing Nginx Proxy Manager + a token.

---

## What the agent reports

`GET /metrics` returns a JSON snapshot:

| Field | Notes |
|-------|-------|
| `host` | hostname, platform, machine, python version, uptime |
| `cpu` | overall %, per-core %, logical/physical core count, load avg, current/max freq |
| `memory` / `swap` | total / used / available / percent |
| `disks[]` | per real mountpoint: device, fstype, total/used/free/percent (pseudo filesystems skipped) |
| `network` | cumulative bytes + live send/recv throughput (bytes/s) |
| `temp_c` | CPU temperature in °C |
| `throttle` | Pi under-voltage / throttling flags (via `vcgencmd get_throttled`) |
| `processes` | process count |

`GET /healthz` → `{"ok": true}` (no auth) for liveness checks.

---

## Packaging the widget into an .exe (optional, later)

`npm start` runs it from source. To build a standalone Windows executable, add
[`electron-builder`](https://www.electron.build/) as a dev dependency and a
`build` script — not set up yet to keep the toolchain minimal.

---

## Troubleshooting

- **Widget shows "disconnected (timeout)"** — agent not running or wrong host/port. Check `sudo systemctl status pi-monitor` on the Pi and confirm the IP in settings. If the PC can't reach the Pi on the LAN at all, check xFi Advanced Security isn't blocking device-to-device traffic (a known gotcha on this network).
- **`temp_c: null`** — rare; the agent tried psutil, sysfs, and `vcgencmd` and got nothing. Confirm `vcgencmd measure_temp` works on the Pi.
- **`ok: false, error: psutil not installed`** — re-run `install.sh` or `sudo apt install python3-psutil`.
