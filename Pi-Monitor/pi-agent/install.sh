#!/usr/bin/env bash
#
# Install the Pi Monitor agent as a systemd service.
# Run ON THE PI from inside the pi-agent/ directory:
#   chmod +x install.sh && ./install.sh
#
# Override the port:  MONITOR_PORT=9000 ./install.sh
# Set a shared token: MONITOR_TOKEN=secret ./install.sh
#
set -euo pipefail

APP_DIR=/opt/pi-monitor
PORT="${MONITOR_PORT:-8080}"
TOKEN="${MONITOR_TOKEN:-}"
SERVICE_USER="$(whoami)"
SRC_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "==> Installing Pi Monitor agent"
echo "    dir:  $APP_DIR"
echo "    user: $SERVICE_USER"
echo "    port: $PORT"
echo "    token: $([ -n "$TOKEN" ] && echo set || echo none)"

# 1. Ensure psutil is available (system package — no venv required).
if ! python3 -c "import psutil" 2>/dev/null; then
  echo "==> Installing python3-psutil"
  sudo apt-get update -qq
  sudo apt-get install -y python3-psutil
fi

# 2. Copy the agent.
sudo mkdir -p "$APP_DIR"
sudo cp "$SRC_DIR/pi_monitor.py" "$APP_DIR/pi_monitor.py"
sudo chmod 644 "$APP_DIR/pi_monitor.py"

# 3. Write the systemd unit (with the resolved user/port/token).
TOKEN_LINE=""
if [ -n "$TOKEN" ]; then
  TOKEN_LINE="Environment=MONITOR_TOKEN=$TOKEN"
fi

sudo tee /etc/systemd/system/pi-monitor.service >/dev/null <<EOF
[Unit]
Description=Pi Monitor agent (system metrics for desktop widget)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$SERVICE_USER
ExecStart=/usr/bin/python3 $APP_DIR/pi_monitor.py
Restart=always
RestartSec=3
Environment=MONITOR_PORT=$PORT
$TOKEN_LINE

[Install]
WantedBy=multi-user.target
EOF

# 4. Enable + start.
sudo systemctl daemon-reload
sudo systemctl enable --now pi-monitor.service

echo
echo "==> Done."
echo "    Status:  sudo systemctl status pi-monitor"
echo "    Logs:    journalctl -u pi-monitor -f"
echo "    Test:    curl http://localhost:$PORT/metrics"
