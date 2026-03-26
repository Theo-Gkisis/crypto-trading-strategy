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
# VPC & NETWORKING
# ----------------------------------------------------------

resource "aws_default_vpc" "default" {}

resource "aws_security_group" "trading_bot" {
  name        = "trading-bot-sg"
  description = "Security group for trading bot"
  vpc_id      = aws_default_vpc.default.id

  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "SSH"
  }

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
  ami                    = "ami-0d1b55a6d77a0c326"
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

