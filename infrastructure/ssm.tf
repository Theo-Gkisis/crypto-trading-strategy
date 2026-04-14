# =============================================================================
# SSM PARAMETER STORE — Secure secrets storage
#
# Instead of putting API keys in plaintext on the server or in git,
# we store them encrypted in AWS SSM Parameter Store.
#
# The EC2 instance pulls them at boot time via its IAM Role (no credentials needed).
# Path format: /{project}/{environment}/{KEY_NAME}
# Example:     /trading-bot/production/BINANCE_API_KEY
# =============================================================================

locals {
  # All secrets as a map for DRY code.
  # key   = environment variable name in .env
  # value = value from terraform.tfvars
  secrets = {
    BINANCE_API_KEY            = var.binance_api_key
    BINANCE_API_SECRET         = var.binance_api_secret
    BINANCE_API_KEY_TESTNET    = var.binance_api_key_testnet
    BINANCE_API_SECRET_TESTNET = var.binance_api_secret_testnet
    TELEGRAM_BOT_TOKEN         = var.telegram_bot_token
    TELEGRAM_CHAT_ID           = var.telegram_chat_id
    TRADING_MODE               = var.trading_mode
    TOTAL_CAPITAL              = tostring(var.total_capital)
    AWS_S3_BUCKET              = var.s3_bucket_name
    AWS_REGION                 = var.aws_region
  }
}

# Creates one SSM parameter per secret automatically
resource "aws_ssm_parameter" "secrets" {
  for_each = local.secrets

  name        = "${local.ssm_prefix}/${each.key}"
  description = "Trading bot secret: ${each.key}"
  type        = "SecureString" # KMS-encrypted at rest
  value       = each.value

  tags = {
    Name = "${local.name_prefix}-${lower(replace(each.key, "_", "-"))}"
  }
}
