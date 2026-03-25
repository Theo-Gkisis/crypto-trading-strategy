output "instance_id" {
  description = "EC2 Instance ID"
  value       = aws_instance.trading_bot.id
}

output "public_ip" {
  description = "Public IP του server"
  value       = aws_eip.trading_bot.public_ip
}

output "ssh_command" {
  description = "Εντολή για σύνδεση SSH"
  value       = "ssh -i ~/.ssh/id_rsa ubuntu@${aws_eip.trading_bot.public_ip}"
}

output "s3_bucket" {
  description = "S3 bucket για backups"
  value       = aws_s3_bucket.backups.bucket
}

output "bot_status_command" {
  description = "Εντολή για να δεις αν τρέχει ο bot"
  value       = "ssh -i ~/.ssh/id_rsa ubuntu@${aws_eip.trading_bot.public_ip} 'sudo systemctl status trading-bot'"
}

output "bot_logs_command" {
  description = "Εντολή για να δεις τα logs"
  value       = "ssh -i ~/.ssh/id_rsa ubuntu@${aws_eip.trading_bot.public_ip} 'sudo journalctl -u trading-bot -f'"
}
