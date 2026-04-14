# =============================================================================
# EC2 — Instance, Key Pair, Elastic IP
# =============================================================================

# -----------------------------------------------------------------------------
# SSH Key Pair
# Uploads your public key to AWS for SSH access
# -----------------------------------------------------------------------------

resource "aws_key_pair" "bot" {
  key_name   = "${local.name_prefix}-key"
  public_key = var.ssh_public_key
}

# -----------------------------------------------------------------------------
# EC2 Instance
# -----------------------------------------------------------------------------

resource "aws_instance" "bot" {
  ami           = data.aws_ami.ubuntu.id
  instance_type = var.instance_type

  # Network & access
  key_name               = aws_key_pair.bot.key_name
  vpc_security_group_ids = [aws_security_group.bot.id]

  # IAM Role — allows the EC2 to write to S3 and read SSM secrets
  iam_instance_profile = aws_iam_instance_profile.bot.name

  # Root disk — 20GB (sufficient for the bot + logs)
  root_block_device {
    volume_type           = "gp3"
    volume_size           = 20
    delete_on_termination = true

    tags = {
      Name = "${local.name_prefix}-disk"
    }
  }

  # Bootstrap script — runs once on first boot.
  # Installs the bot and starts it as a systemd service.
  user_data = templatefile("${path.module}/user_data.sh", {
    repo_url    = var.github_repo_url
    repo_branch = var.github_branch
    aws_region  = var.aws_region
    ssm_prefix  = local.ssm_prefix
  })

  # If user_data changes, create a new instance rather than updating in place
  # (user_data only runs on first boot)
  lifecycle {
    create_before_destroy = true
  }

  tags = {
    Name = "${local.name_prefix}-instance"
  }
}

# -----------------------------------------------------------------------------
# Elastic IP
# Static IP — does not change when the instance restarts.
# Free while attached to a running instance.
# -----------------------------------------------------------------------------

resource "aws_eip" "bot" {
  instance = aws_instance.bot.id
  domain   = "vpc"

  depends_on = [aws_instance.bot]

  tags = {
    Name = "${local.name_prefix}-eip"
  }
}
