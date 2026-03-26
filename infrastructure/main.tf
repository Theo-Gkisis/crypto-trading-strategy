terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# ----------------------------------------------------------
# DATA SOURCES
# ----------------------------------------------------------


# ----------------------------------------------------------
# DATA SOURCES
# ----------------------------------------------------------

data "aws_ami" "amazon_linux" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-2023.*-x86_64"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

# ----------------------------------------------------------
# VPC & NETWORKING
# ----------------------------------------------------------

resource "aws_default_vpc" "default" {}

resource "aws_security_group" "trading_bot" {
  name        = "trading-bot-sg"
  description = "Security group for trading bot"
  vpc_id      = aws_default_vpc.default.id

  # SSH access
  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "SSH"
  }

  # Outbound (bot needs internet για Binance API)
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "All outbound"
  }

  tags = {
    Name    = "trading-bot-sg"
    Project = "trading-bot"
  }
}

# ----------------------------------------------------------
# IAM ROLE (EC2 → S3 access)
# ----------------------------------------------------------

resource "aws_iam_role" "trading_bot" {
  name = "trading-bot-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
    }]
  })

  tags = {
    Name    = "trading-bot-role"
    Project = "trading-bot"
  }
}

resource "aws_iam_role_policy" "trading_bot_s3" {
  name = "trading-bot-s3-policy"
  role = aws_iam_role.trading_bot.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:GetObject",
          "s3:DeleteObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.backups.arn,
          "${aws_s3_bucket.backups.arn}/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "cloudwatch:PutMetricData",
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "*"
      }
    ]
  })
}

resource "aws_iam_instance_profile" "trading_bot" {
  name = "trading-bot-profile"
  role = aws_iam_role.trading_bot.name
}

# ----------------------------------------------------------
# S3 BUCKET (database backups)
# ----------------------------------------------------------

resource "aws_s3_bucket" "backups" {
  bucket = var.s3_bucket_name

  tags = {
    Name    = "trading-bot-backups"
    Project = "trading-bot"
  }
}

resource "aws_s3_bucket_versioning" "backups" {
  bucket = aws_s3_bucket.backups.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "backups" {
  bucket = aws_s3_bucket.backups.id

  rule {
    id     = "delete-old-backups"
    status = "Enabled"

    filter {
      prefix = "backups/"
    }

    expiration {
      days = 30
    }
  }
}

resource "aws_s3_bucket_public_access_block" "backups" {
  bucket                  = aws_s3_bucket.backups.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# ----------------------------------------------------------
# EC2 INSTANCE
# ----------------------------------------------------------

resource "aws_key_pair" "trading_bot" {
  key_name   = "trading-bot-key"
  public_key = file(pathexpand(var.ssh_public_key_path))

  tags = {
    Name    = "trading-bot-key"
    Project = "trading-bot"
  }
}

resource "aws_instance" "trading_bot" {
  ami                    = data.aws_ami.amazon_linux.id
  instance_type          = var.instance_type
  key_name               = aws_key_pair.trading_bot.key_name
  vpc_security_group_ids = [aws_security_group.trading_bot.id]
  iam_instance_profile   = aws_iam_instance_profile.trading_bot.name

  user_data = templatefile("${path.module}/user_data.sh", {
    binance_api_key         = var.binance_api_key
    binance_api_secret      = var.binance_api_secret
    binance_api_key_test    = var.binance_api_key_testnet
    binance_api_secret_test = var.binance_api_secret_testnet
    telegram_token          = var.telegram_bot_token
    telegram_chat_id        = var.telegram_chat_id
    s3_bucket               = var.s3_bucket_name
    aws_region              = var.aws_region
    trading_mode            = var.trading_mode
    total_capital           = var.total_capital
    github_username         = lower(var.github_username)
    github_repo             = lower(var.github_repo)
  })

  root_block_device {
    volume_size = 20
    volume_type = "gp3"
  }

  tags = {
    Name    = "trading-bot"
    Project = "trading-bot"
  }
}

# ----------------------------------------------------------
# ELASTIC IP (σταθερή IP)
# ----------------------------------------------------------

resource "aws_eip" "trading_bot" {
  instance = aws_instance.trading_bot.id
  domain   = "vpc"

  tags = {
    Name    = "trading-bot-eip"
    Project = "trading-bot"
  }
}

# ----------------------------------------------------------
# CLOUDWATCH (monitoring)
# ----------------------------------------------------------

resource "aws_cloudwatch_metric_alarm" "cpu_high" {
  alarm_name          = "trading-bot-cpu-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "CPUUtilization"
  namespace           = "AWS/EC2"
  period              = 300
  statistic           = "Average"
  threshold           = 80
  alarm_description   = "CPU πάνω από 80%"

  dimensions = {
    InstanceId = aws_instance.trading_bot.id
  }

  tags = {
    Project = "trading-bot"
  }
}

resource "aws_cloudwatch_metric_alarm" "instance_down" {
  alarm_name          = "trading-bot-instance-down"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 2
  metric_name         = "StatusCheckFailed"
  namespace           = "AWS/EC2"
  period              = 60
  statistic           = "Maximum"
  threshold           = 1
  alarm_description   = "EC2 instance είναι down!"

  dimensions = {
    InstanceId = aws_instance.trading_bot.id
  }

  tags = {
    Project = "trading-bot"
  }
}
