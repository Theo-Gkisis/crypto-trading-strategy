# Infrastructure — Terraform

Provisions the AWS infrastructure needed to run the trading bot on a single EC2 instance.

---

## What gets created

| Resource | Type | Purpose |
|---|---|---|
| `aws_instance` | EC2 t2.micro | The server that runs the bot 24/7 |
| `aws_eip` | Elastic IP | Static public IP (doesn't change on restart) |
| `aws_key_pair` | Key Pair | Your SSH public key for server access |
| `aws_security_group` | Firewall | SSH from your IP only, unrestricted outbound |
| `aws_iam_role` | IAM Role | Allows EC2 to access S3 and SSM (no hardcoded keys) |
| `aws_s3_bucket` | S3 | Stores hourly database backups |
| `aws_ssm_parameter` | SSM (×10) | Stores all secrets encrypted (API keys, tokens) |

**Estimated cost:** Free for 12 months (AWS Free Tier), then ~$8.50/month.

---

## How deployment works

```
terraform apply
      │
      ├── Creates all AWS resources
      │
      └── EC2 runs user_data.sh on first boot:
            ├── Installs Python 3.11, git, awscli
            ├── Clones the repo from GitHub
            ├── pip install -r requirements.txt
            ├── Pulls secrets from SSM → writes .env
            └── Registers and starts trading-bot.service (systemd)
```

After `apply` completes, the bot is running. No manual SSH needed.

---

## Prerequisites

Before running Terraform, make sure you have:

- [ ] [Terraform >= 1.6](https://developer.hashicorp.com/terraform/install) installed
- [ ] [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/install-cliv2.html) installed and configured (`aws configure`)
- [ ] An SSH key pair on your machine (`~/.ssh/id_rsa` + `~/.ssh/id_rsa.pub`)
- [ ] Your AWS Free Tier account active
- [ ] The repo pushed to GitHub

---

## File structure

```
infrastructure/
├── main.tf                   # AWS provider, locals, Ubuntu AMI data source
├── variables.tf              # All input variables with descriptions and defaults
├── ec2.tf                    # EC2 instance, Key Pair, Elastic IP
├── security_group.tf         # Inbound/outbound firewall rules
├── iam.tf                    # IAM Role, policies for S3 + SSM access
├── s3.tf                     # Backup bucket, versioning, lifecycle, encryption
├── ssm.tf                    # Encrypted secrets in Parameter Store
├── outputs.tf                # IP address, SSH command printed after apply
├── user_data.sh              # Bootstrap script (runs on first EC2 boot)
├── terraform.tfvars.example  # Template for your values (safe to commit)
└── .gitignore                # Excludes terraform.tfvars and state files
```

---

## Deploy

### Step 1 — Configure your variables

```bash
cd infrastructure
cp terraform.tfvars.example terraform.tfvars
```

Open `terraform.tfvars` and fill in every value:

```hcl
# Your public IP (restrict SSH access to only you)
your_ip = "x.x.x.x/32"         # curl ifconfig.me

# Your SSH public key
ssh_public_key = "ssh-rsa AAA..." # cat ~/.ssh/id_rsa.pub

# Secrets
binance_api_key    = "..."
binance_api_secret = "..."
telegram_bot_token = "..."
telegram_chat_id   = "..."
# ... (see terraform.tfvars.example for the full list)
```

> `terraform.tfvars` is gitignored — it will never be committed.

---

### Step 2 — Initialise Terraform

Downloads the AWS provider plugin.

```bash
terraform init
```

---

### Step 3 — Preview the changes

Shows exactly what will be created before touching anything.

```bash
terraform plan
```

---

### Step 4 — Deploy

Creates all resources and starts the bot.

```bash
terraform apply
```

Type `yes` when prompted. Takes ~2 minutes.

**Example output after apply:**

```
Outputs:

instance_public_ip = "18.184.x.x"
ssh_command        = "ssh -i ~/.ssh/id_rsa ubuntu@18.184.x.x"
check_bot_logs     = "ssh -i ~/.ssh/id_rsa ubuntu@18.184.x.x 'sudo journalctl -u trading-bot -f'"
check_bot_status   = "ssh -i ~/.ssh/id_rsa ubuntu@18.184.x.x 'sudo systemctl status trading-bot'"
s3_bucket_name     = "theodorosgkisi23bucket"
ssm_prefix         = "/trading-bot/production"
```

---

## Verify the bot is running

After `apply`, wait ~3 minutes for the bootstrap script to finish, then:

```bash
# Check service status
ssh -i ~/.ssh/id_rsa ubuntu@<IP> 'sudo systemctl status trading-bot'

# Stream live logs
ssh -i ~/.ssh/id_rsa ubuntu@<IP> 'sudo journalctl -u trading-bot -f'

# Check bootstrap log (if something went wrong)
ssh -i ~/.ssh/id_rsa ubuntu@<IP> 'cat /var/log/user_data.log'
```

---

## Useful commands (on the server)

```bash
# Stop the bot
sudo systemctl stop trading-bot

# Start the bot
sudo systemctl start trading-bot

# Restart the bot
sudo systemctl restart trading-bot

# View last 100 log lines
sudo journalctl -u trading-bot -n 100
```

---

## Tear down

Destroys all AWS resources (except the S3 bucket if it contains files).

```bash
terraform destroy
```

> The S3 bucket has `force_destroy = false` to protect your backups.
> Empty the bucket manually first if you want it deleted too.
