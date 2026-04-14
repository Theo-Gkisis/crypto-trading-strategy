# =============================================================================
# VARIABLES
# All infrastructure parameters defined in one place.
# Values go in terraform.tfvars (never committed to git)
# =============================================================================

# -----------------------------------------------------------------------------
# GENERAL
# -----------------------------------------------------------------------------

variable "project_name" {
  description = "Project name — used in resource names and tags"
  type        = string
  default     = "trading-bot"
}

variable "environment" {
  description = "Deployment environment (production / staging)"
  type        = string
  default     = "production"

  validation {
    condition     = contains(["production", "staging"], var.environment)
    error_message = "Allowed values: production, staging."
  }
}

variable "aws_region" {
  description = "AWS region where resources will be created"
  type        = string
  default     = "eu-central-1" # Frankfurt — closest to Greece
}

# -----------------------------------------------------------------------------
# EC2
# -----------------------------------------------------------------------------

variable "instance_type" {
  description = "EC2 instance type (t2.micro = free tier eligible)"
  type        = string
  default     = "t2.micro"
}

variable "ssh_public_key" {
  description = "Your SSH public key content (contents of ~/.ssh/id_rsa.pub)"
  type        = string
  sensitive   = true
}

variable "your_ip" {
  description = "Your public IP for SSH access (x.x.x.x/32). Find it with: curl ifconfig.me"
  type        = string

  validation {
    condition     = can(regex("^\\d+\\.\\d+\\.\\d+\\.\\d+/\\d+$", var.your_ip))
    error_message = "Must be in CIDR format, e.g. 203.0.113.5/32"
  }
}

# -----------------------------------------------------------------------------
# GITHUB REPO
# -----------------------------------------------------------------------------

variable "github_repo_url" {
  description = "GitHub repo URL (HTTPS for public repos, SSH for private)"
  type        = string
  default     = "https://github.com/TheodoreGisis/AI-TRADING-BOT.git"
}

variable "github_branch" {
  description = "Branch to clone onto the EC2 instance"
  type        = string
  default     = "main"
}

# -----------------------------------------------------------------------------
# S3 BACKUP
# -----------------------------------------------------------------------------

variable "s3_bucket_name" {
  description = "S3 bucket name for database backups (must be globally unique)"
  type        = string
  default     = "theodorosgkisi23bucket"
}

variable "s3_backup_retention_days" {
  description = "Number of days to retain backup files in S3 before auto-deletion"
  type        = number
  default     = 30
}

# -----------------------------------------------------------------------------
# BOT SETTINGS (stored as SSM Parameters)
# -----------------------------------------------------------------------------

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

variable "telegram_bot_token" {
  description = "Telegram Bot Token for notifications"
  type        = string
  sensitive   = true
}

variable "telegram_chat_id" {
  description = "Telegram Chat ID for notifications"
  type        = string
  sensitive   = true
}

variable "trading_mode" {
  description = "Trading mode: live or testnet"
  type        = string
  default     = "testnet"

  validation {
    condition     = contains(["live", "testnet"], var.trading_mode)
    error_message = "Allowed values: live, testnet."
  }
}

variable "total_capital" {
  description = "Total capital in USD managed by the bot"
  type        = number
  default     = 100
}
