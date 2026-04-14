# =============================================================================
# IAM — Permissions for the EC2 instance
#
# The EC2 needs two capabilities:
#   1. Write database backups to S3
#   2. Read secrets from SSM Parameter Store
#
# Using an IAM Role means no hardcoded credentials on the server.
# =============================================================================

# -----------------------------------------------------------------------------
# IAM Role
# The "identity" assumed by the EC2 instance
# -----------------------------------------------------------------------------

resource "aws_iam_role" "bot" {
  name        = "${local.name_prefix}-role"
  description = "Allows the trading bot to access S3 and SSM"

  # Trust policy — who is allowed to assume this role
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect    = "Allow"
        Principal = { Service = "ec2.amazonaws.com" }
        Action    = "sts:AssumeRole"
      }
    ]
  })
}

# -----------------------------------------------------------------------------
# IAM Policy — S3 Backup
# Read/write access scoped to the specific backup bucket only
# -----------------------------------------------------------------------------

resource "aws_iam_role_policy" "s3_backup" {
  name = "${local.name_prefix}-s3-backup"
  role = aws_iam_role.bot.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "S3BackupAccess"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.backup.arn,
          "${aws_s3_bucket.backup.arn}/*"
        ]
      }
    ]
  })
}

# -----------------------------------------------------------------------------
# IAM Policy — SSM Parameter Store
# Read-only access scoped to this project's secret path only
# -----------------------------------------------------------------------------

resource "aws_iam_role_policy" "ssm_secrets" {
  name = "${local.name_prefix}-ssm-secrets"
  role = aws_iam_role.bot.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "SSMReadSecrets"
        Effect = "Allow"
        Action = [
          "ssm:GetParameter",
          "ssm:GetParameters",
          "ssm:GetParametersByPath"
        ]
        # Scoped to this project's prefix only (e.g. /trading-bot/production/*)
        Resource = "arn:aws:ssm:${var.aws_region}:*:parameter${local.ssm_prefix}/*"
      },
      {
        Sid      = "KMSDecrypt"
        Effect   = "Allow"
        Action   = ["kms:Decrypt"]
        Resource = "*" # Required for SecureString parameters (KMS-encrypted)
      }
    ]
  })
}

# -----------------------------------------------------------------------------
# Instance Profile
# The bridge between EC2 and the IAM Role — required for attachment
# -----------------------------------------------------------------------------

resource "aws_iam_instance_profile" "bot" {
  name = "${local.name_prefix}-profile"
  role = aws_iam_role.bot.name
}
