# =============================================================================
# S3 — Bucket for database backups
# The bot (via boto3) uploads the SQLite .db file here every hour
# =============================================================================

resource "aws_s3_bucket" "backup" {
  bucket = var.s3_bucket_name

  # WARNING: force_destroy = true will delete all backups on terraform destroy.
  # Set to false in production to protect your data.
  force_destroy = false

  tags = {
    Name    = "${local.name_prefix}-backup"
    Purpose = "Database backups"
  }
}

# -----------------------------------------------------------------------------
# Block Public Access — bucket must never be publicly accessible
# -----------------------------------------------------------------------------

resource "aws_s3_bucket_public_access_block" "backup" {
  bucket = aws_s3_bucket.backup.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# -----------------------------------------------------------------------------
# Versioning — keeps a history of every backup file version.
# Allows restoring a previous version if something goes wrong.
# -----------------------------------------------------------------------------

resource "aws_s3_bucket_versioning" "backup" {
  bucket = aws_s3_bucket.backup.id

  versioning_configuration {
    status = "Enabled"
  }
}

# -----------------------------------------------------------------------------
# Lifecycle — auto-delete old backups to avoid unnecessary storage costs
# -----------------------------------------------------------------------------

resource "aws_s3_bucket_lifecycle_configuration" "backup" {
  bucket = aws_s3_bucket.backup.id

  rule {
    id     = "delete-old-backups"
    status = "Enabled"

    # Delete current versions after N days
    expiration {
      days = var.s3_backup_retention_days
    }

    # Delete non-current (versioned) copies after 7 days
    noncurrent_version_expiration {
      noncurrent_days = 7
    }
  }
}

# -----------------------------------------------------------------------------
# Encryption — encrypt backups at rest using AES-256
# -----------------------------------------------------------------------------

resource "aws_s3_bucket_server_side_encryption_configuration" "backup" {
  bucket = aws_s3_bucket.backup.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}
