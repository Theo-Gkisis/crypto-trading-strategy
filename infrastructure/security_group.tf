# =============================================================================
# SECURITY GROUP — Firewall rules for the EC2 instance
# =============================================================================

resource "aws_security_group" "bot" {
  name        = "${local.name_prefix}-sg"
  description = "Trading bot firewall — SSH from your IP only, unrestricted outbound"

  # --------------------------------------------------------------------------
  # INBOUND — what is allowed to reach the server
  # --------------------------------------------------------------------------

  # SSH restricted to your IP only (never 0.0.0.0/0 — no open access)
  ingress {
    description = "SSH access from admin only"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.your_ip]
  }

  # --------------------------------------------------------------------------
  # OUTBOUND — what the server is allowed to reach
  # --------------------------------------------------------------------------

  # The bot needs to communicate with:
  # - Binance API   (HTTPS 443)
  # - Telegram API  (HTTPS 443)
  # - AWS S3        (HTTPS 443)
  # - GitHub        (HTTPS 443, for git clone)
  # - apt           (HTTP 80,  for package installation)
  egress {
    description = "Outbound traffic — Binance, Telegram, S3, GitHub, apt"
    from_port   = 0
    to_port     = 0
    protocol    = "-1" # All protocols
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${local.name_prefix}-sg"
  }
}
