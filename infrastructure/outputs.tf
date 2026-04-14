# =============================================================================
# OUTPUTS — Information printed after terraform apply
# =============================================================================

output "instance_public_ip" {
  description = "Static public IP of the server (Elastic IP)"
  value       = aws_eip.bot.public_ip
}

output "ssh_command" {
  description = "Ready-to-use SSH command to connect to the server"
  value       = "ssh -i ~/.ssh/id_rsa ubuntu@${aws_eip.bot.public_ip}"
}

output "instance_id" {
  description = "AWS Instance ID (for use in the console)"
  value       = aws_instance.bot.id
}

output "s3_bucket_name" {
  description = "S3 bucket name used for backups"
  value       = aws_s3_bucket.backup.id
}

output "check_bot_logs" {
  description = "Command to stream live bot logs"
  value       = "ssh -i ~/.ssh/id_rsa ubuntu@${aws_eip.bot.public_ip} 'sudo journalctl -u trading-bot -f'"
}

output "check_bot_status" {
  description = "Command to check whether the bot is running"
  value       = "ssh -i ~/.ssh/id_rsa ubuntu@${aws_eip.bot.public_ip} 'sudo systemctl status trading-bot'"
}

output "ssm_prefix" {
  description = "SSM Parameter Store path prefix where secrets are stored"
  value       = local.ssm_prefix
}
