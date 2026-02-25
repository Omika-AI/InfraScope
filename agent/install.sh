#!/bin/bash
set -e

echo "=== InfraScope Agent Installer ==="
echo ""

# Prompt for configuration
read -rp "InfraScope URL (e.g., http://infrascope.example.com:8000): " INFRASCOPE_URL
read -rp "Agent Secret: " AGENT_SECRET

# Create installation directory
INSTALL_DIR="/opt/infrascope"
mkdir -p "$INSTALL_DIR"

# Copy agent
cp "$(dirname "$0")/infrascope-agent.py" "$INSTALL_DIR/infrascope-agent.py"
chmod +x "$INSTALL_DIR/infrascope-agent.py"

# Install psutil
pip3 install psutil 2>/dev/null || pip install psutil

# Create environment file
cat > "$INSTALL_DIR/.env" <<EOF
INFRASCOPE_URL=${INFRASCOPE_URL}
AGENT_SECRET=${AGENT_SECRET}
REPORT_INTERVAL=60
EOF

# Install systemd service
cat > /etc/systemd/system/infrascope-agent.service <<EOF
[Unit]
Description=InfraScope Monitoring Agent
After=network.target

[Service]
Type=simple
EnvironmentFile=${INSTALL_DIR}/.env
ExecStart=/usr/bin/python3 ${INSTALL_DIR}/infrascope-agent.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Enable and start service
systemctl daemon-reload
systemctl enable infrascope-agent
systemctl start infrascope-agent

echo ""
echo "=== InfraScope Agent installed and running ==="
echo "Check status: systemctl status infrascope-agent"
echo "View logs:    journalctl -u infrascope-agent -f"
