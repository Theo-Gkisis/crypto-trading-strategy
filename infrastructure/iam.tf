# ----------------------------------------------------------
# IAM ROLE (EC2 → S3 + CloudWatch access)
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
