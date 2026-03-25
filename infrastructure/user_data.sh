#!/bin/bash
set -e

# ----------------------------------------------------------
# TRADING BOT - EC2 User Data Script
# Τρέχει αυτόματα όταν ξεκινά το EC2 instance
# ----------------------------------------------------------

echo "=== Trading Bot Setup Starting ==="

# Update system
apt-get update -y
apt-get upgrade -y
apt-get install -y python3 python3-pip python3-venv git curl unzip

# Install AWS CLI
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
./install
rm -rf awscliv2.zip aws

# Create bot user
useradd -m -s /bin/bash botuser || true

# Create project directory
mkdir -p /home/botuser/AI-TRADING-BOT
chown botuser:botuser /home/botuser/AI-TRADING-BOT

# ----------------------------------------------------------
# ΚΑΤΕΒΑΣΜΑ ΚΩΔΙΚΑ ΑΠΟ S3
# (θα ανεβάσουμε τον κώδικα στο S3 μετά)
# ----------------------------------------------------------
aws s3 cp s3://${s3_bucket}/code/trading-bot.zip /tmp/trading-bot.zip --region ${aws_region} || true

if [ -f /tmp/trading-bot.zip ]; then
    unzip -o /tmp/trading-bot.zip -d /home/botuser/AI-TRADING-BOT
    chown -R botuser:botuser /home/botuser/AI-TRADING-BOT
fi

# ----------------------------------------------------------
# PYTHON VIRTUAL ENVIRONMENT
# ----------------------------------------------------------
cd /home/botuser/AI-TRADING-BOT
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip

if [ -f requirements.txt ]; then
    pip install -r requirements.txt
fi

# ----------------------------------------------------------
# ENVIRONMENT VARIABLES (.env file)
# ----------------------------------------------------------
cat > /home/botuser/AI-TRADING-BOT/.env << 'ENVFILE'
# Binance Live
BINANCE_API_KEY=${binance_api_key}
BINANCE_API_SECRET=${binance_api_secret}

# Binance Testnet
BINANCE_API_KEY_TESTNET=${binance_api_key_test}
BINANCE_API_SECRET_TESTNET=${binance_api_secret_test}

# Telegram
TELEGRAM_BOT_TOKEN=${telegram_token}
TELEGRAM_CHAT_ID=${telegram_chat_id}

# AWS S3
AWS_S3_BUCKET=${s3_bucket}
AWS_REGION=${aws_region}

# Trading Config
TRADING_MODE=${trading_mode}
TOTAL_CAPITAL=${total_capital}
ENVFILE

chown botuser:botuser /home/botuser/AI-TRADING-BOT/.env
chmod 600 /home/botuser/AI-TRADING-BOT/.env

# ----------------------------------------------------------
# SYSTEMD SERVICE (auto-start + auto-restart)
# ----------------------------------------------------------
cat > /etc/systemd/system/trading-bot.service << 'SERVICEFILE'
[Unit]
Description=AI Trading Bot
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=botuser
WorkingDirectory=/home/botuser/AI-TRADING-BOT
ExecStart=/home/botuser/AI-TRADING-BOT/venv/bin/python -X utf8 main.py
Restart=always
RestartSec=30
StandardOutput=journal
StandardError=journal
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
SERVICEFILE

# Enable και start service
systemctl daemon-reload
systemctl enable trading-bot
systemctl start trading-bot

echo "=== Trading Bot Setup Complete ==="
echo "Status: $(systemctl is-active trading-bot)"
