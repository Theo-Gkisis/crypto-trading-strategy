output "instance_id" {
  description = "EC2 Instance ID"
  value       = aws_instance.trading_bot.id
}

output "public_ip" {
  description = "Public IP"
  value       = aws_instance.trading_bot.public_ip
}

output "ssh_command" {
  description = "SSH command"
  value       = "ssh -i ~/.ssh/id_rsa ec2-user@${aws_instance.trading_bot.public_ip}"
}

output "s3_bucket" {
  description = "S3 bucket για backups"
  value       = aws_s3_bucket.backups.bucket
}
