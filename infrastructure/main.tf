# =============================================================================
# MAIN — Provider & Locals
# =============================================================================

terraform {
  required_version = ">= 1.6"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # State is stored locally (terraform.tfstate).
  # For team collaboration, replace with an S3 backend:
  #
  # backend "s3" {
  #   bucket = "my-terraform-state"
  #   key    = "trading-bot/terraform.tfstate"
  #   region = "eu-central-1"
  # }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = local.common_tags
  }
}

# -----------------------------------------------------------------------------
# LOCALS — shared values used across all files
# -----------------------------------------------------------------------------

locals {
  # Resource name prefix: "trading-bot-production"
  name_prefix = "${var.project_name}-${var.environment}"

  # SSM path prefix for secrets: "/trading-bot/production/"
  ssm_prefix = "/${var.project_name}/${var.environment}"

  # Tags applied to all resources automatically via default_tags
  common_tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

# -----------------------------------------------------------------------------
# DATA SOURCE — Automatically finds the latest Ubuntu 22.04 LTS AMI
# -----------------------------------------------------------------------------

data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"] # Canonical (official Ubuntu publisher)

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}
