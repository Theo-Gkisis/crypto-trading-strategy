#!/bin/bash
set -e

echo "=== Trading Bot Docker Setup ==="

# Update system
dnf update -y

# Install Docker
dnf install -y docker
systemctl enable docker
systemctl start docker
usermod -aG docker ec2-user

# Install Docker Compose plugin
mkdir -p /usr/local/lib/docker/cli-plugins
curl -SL https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64 \
  -o /usr/local/lib/docker/cli-plugins/docker-compose
chmod +x /usr/local/lib/docker/cli-plugins/docker-compose

# Create project directory
mkdir -p /home/ec2-user/AI-TRADING-BOT
cd /home/ec2-user/AI-TRADING-BOT

# Create .env file
cat > .env << 'ENVFILE'
BINANCE_API_KEY=${binance_api_key}
BINANCE_API_SECRET=${binance_api_secret}
BINANCE_API_KEY_TESTNET=${binance_api_key_test}
BINANCE_API_SECRET_TESTNET=${binance_api_secret_test}
TELEGRAM_BOT_TOKEN=${telegram_token}
TELEGRAM_CHAT_ID=${telegram_chat_id}
AWS_S3_BUCKET=${s3_bucket}
AWS_REGION=${aws_region}
TRADING_MODE=${trading_mode}
TOTAL_CAPITAL=${total_capital}
ENVFILE

chmod 600 .env

# Create docker-compose.yml
cat > docker-compose.yml << 'COMPOSEFILE'
services:
  trading-bot:
    image: ${github_username}/${github_repo}:latest
    container_name: trading-bot
    restart: unless-stopped
    env_file:
      - .env
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
COMPOSEFILE

# Pull & Start bot
docker compose pull
docker compose up -d

echo "=== Setup Complete ==="
docker compose ps
