variable "github_username" {
  description = "GitHub username"
  type        = string
}

variable "github_repo" {
  description = "GitHub repository name"
  type        = string
  default     = "AI-TRADING-BOT"
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "eu-central-1"
}

variable "instance_type" {
  description = "EC2 instance type (t2.micro = free tier)"
  type        = string
  default     = "t2.micro"
}

variable "s3_bucket_name" {
  description = "Μοναδικό όνομα για το S3 bucket"
  type        = string
}

variable "ssh_public_key_path" {
  description = "Path στο SSH public key (~/.ssh/id_rsa.pub)"
  type        = string
  default     = "~/.ssh/id_rsa.pub"
}

# ----------------------------------------------------------
# TRADING BOT CONFIG
# ----------------------------------------------------------

variable "trading_mode" {
  description = "testnet ή live"
  type        = string
  default     = "testnet"
}

variable "total_capital" {
  description = "Συνολικό κεφάλαιο σε USDT"
  type        = number
  default     = 100
}

# ----------------------------------------------------------
# BINANCE
# ----------------------------------------------------------

variable "binance_api_key" {
  description = "Binance API Key (live)"
  type        = string
  sensitive   = true
}

variable "binance_api_secret" {
  description = "Binance API Secret (live)"
  type        = string
  sensitive   = true
}

variable "binance_api_key_testnet" {
  description = "Binance API Key (testnet)"
  type        = string
  sensitive   = true
}

variable "binance_api_secret_testnet" {
  description = "Binance API Secret (testnet)"
  type        = string
  sensitive   = true
}

# ----------------------------------------------------------
# TELEGRAM
# ----------------------------------------------------------

variable "telegram_bot_token" {
  description = "Telegram Bot Token"
  type        = string
  sensitive   = true
}

variable "telegram_chat_id" {
  description = "Telegram Chat ID"
  type        = string
  sensitive   = true
}
