#!/bin/bash
# =============================================================================
# USER DATA — Bootstrap script
#
# Runs automatically once on the first EC2 boot.
# Installs the bot and starts it as a systemd service.
#
# Variables injected by Terraform via templatefile():
#   ${repo_url}    — GitHub repo URL
#   ${repo_branch} — Branch to clone (default: main)
#   ${aws_region}  — AWS region (for SSM API calls)
#   ${ssm_prefix}  — SSM path prefix (e.g. /trading-bot/production)
# =============================================================================

set -euo pipefail  # Exit immediately if any command fails

# Redirect all output to both the console and a log file
exec > >(tee /var/log/user_data.log | logger -t user_data -s 2>/dev/console) 2>&1

echo "============================================"
echo " Trading Bot — Bootstrap started"
echo " $(date)"
echo "============================================"

# -----------------------------------------------------------------------------
# 1. SYSTEM UPDATE & DEPENDENCIES
# -----------------------------------------------------------------------------

echo "[1/6] Installing system packages..."

apt-get update -y
apt-get install -y \
  python3.11 \
  python3-pip \
  python3.11-venv \
  git \
  awscli \
  --no-install-recommends

echo "Done: system packages installed"

# -----------------------------------------------------------------------------
# 2. CLONE REPO
# -----------------------------------------------------------------------------

echo "[2/6] Cloning repo from GitHub..."

PROJECT_DIR="/home/ubuntu/trading-bot"

sudo -u ubuntu git clone \
  --branch "${repo_branch}" \
  --single-branch \
  "${repo_url}" \
  "$PROJECT_DIR"

echo "Done: repo cloned to $PROJECT_DIR"

# -----------------------------------------------------------------------------
# 3. PYTHON VIRTUAL ENVIRONMENT & DEPENDENCIES
# -----------------------------------------------------------------------------

echo "[3/6] Installing Python dependencies..."

sudo -u ubuntu python3.11 -m venv "$PROJECT_DIR/venv"

sudo -u ubuntu "$PROJECT_DIR/venv/bin/pip" install \
  --upgrade pip \
  --quiet

sudo -u ubuntu "$PROJECT_DIR/venv/bin/pip" install \
  -r "$PROJECT_DIR/bot/requirements.txt" \
  --quiet

echo "Done: Python dependencies installed"

# -----------------------------------------------------------------------------
# 4. BUILD .env FROM SSM PARAMETER STORE
#
# Fetches all secrets under ${ssm_prefix}/* and writes them to .env.
# No credentials needed — uses the EC2's attached IAM Role.
# -----------------------------------------------------------------------------

echo "[4/6] Loading secrets from SSM Parameter Store..."

mkdir -p "$PROJECT_DIR/bot/logs"

ENV_FILE="$PROJECT_DIR/bot/.env"

# Fetch all parameters under the prefix and write KEY=VALUE pairs to .env
aws ssm get-parameters-by-path \
  --path "${ssm_prefix}" \
  --with-decryption \
  --region "${aws_region}" \
  --query "Parameters[*].[Name,Value]" \
  --output text | while IFS=$'\t' read -r name value; do
    # Strip the path prefix, keep only the key name
    # e.g. /trading-bot/production/BINANCE_API_KEY → BINANCE_API_KEY
    key=$(basename "$name")
    echo "$key=$value"
  done > "$ENV_FILE"

chown ubuntu:ubuntu "$ENV_FILE"
chmod 600 "$ENV_FILE"  # Readable only by the ubuntu user

echo "Done: .env created with $(wc -l < "$ENV_FILE") variables"

# -----------------------------------------------------------------------------
# 5. LOGS DIRECTORY
# -----------------------------------------------------------------------------

mkdir -p "$PROJECT_DIR/bot/logs"
chown -R ubuntu:ubuntu "$PROJECT_DIR/bot/logs"

echo "Done: logs directory created"

# -----------------------------------------------------------------------------
# 6. SYSTEMD SERVICE
#
# The bot runs as a system service:
#   - Starts automatically on server boot
#   - Restarts automatically if it crashes (after 30s)
#   - Logs available via: sudo journalctl -u trading-bot -f
# -----------------------------------------------------------------------------

echo "[6/6] Creating systemd service..."

SERVICE_NAME="trading-bot"

cat > "/etc/systemd/system/$SERVICE_NAME.service" << EOF
[Unit]
Description=AI Trading Bot
Documentation=https://github.com/TheodoreGisis/AI-TRADING-BOT
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=$PROJECT_DIR/bot
ExecStart=$PROJECT_DIR/venv/bin/python3 -X utf8 main.py
Restart=always
RestartSec=30
StandardOutput=journal
StandardError=journal
SyslogIdentifier=$SERVICE_NAME
Environment=PYTHONUNBUFFERED=1
Environment=PYTHONDONTWRITEBYTECODE=1

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable "$SERVICE_NAME"
systemctl start "$SERVICE_NAME"

echo "Done: service $SERVICE_NAME started"

# -----------------------------------------------------------------------------
# DONE
# -----------------------------------------------------------------------------

echo ""
echo "============================================"
echo " Bootstrap completed successfully!"
echo " $(date)"
echo ""
echo " Useful commands:"
echo "   Logs:   sudo journalctl -u $SERVICE_NAME -f"
echo "   Status: sudo systemctl status $SERVICE_NAME"
echo "   Stop:   sudo systemctl stop $SERVICE_NAME"
echo "============================================"
