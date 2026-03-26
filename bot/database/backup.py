"""
S3 Backup Module

Κάνει backup της SQLite database στο AWS S3 κάθε ώρα.
Κρατάει τα τελευταία 7 ημέρες backups αυτόματα.
"""
import os
import logging
import boto3
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

DB_PATH      = "data/trading_bot.db"
AWS_BUCKET   = os.getenv("AWS_S3_BUCKET", "")
AWS_REGION   = os.getenv("AWS_REGION", "eu-west-1")
KEEP_DAYS    = 7  # Κρατάει backups για 7 μέρες


class S3Backup:

    def __init__(self):
        self.enabled = bool(AWS_BUCKET)

        if self.enabled:
            # Χρησιμοποιεί IAM Role αυτόματα (EC2) ή local AWS credentials
            self.client = boto3.client("s3", region_name=AWS_REGION)
            logger.info(f"S3 Backup enabled → bucket: {AWS_BUCKET}")
        else:
            logger.warning("S3 Backup disabled — έλεγξε AWS_S3_BUCKET στο .env")

    def backup(self) -> bool:
        """
        Ανεβάζει το trading_bot.db στο S3.
        Όνομα αρχείου: trading_bot_2026-03-20_14-30.db
        """
        if not self.enabled:
            return False

        if not os.path.exists(DB_PATH):
            logger.warning(f"Database δεν βρέθηκε: {DB_PATH}")
            return False

        try:
            timestamp   = datetime.now().strftime("%Y-%m-%d_%H-%M")
            s3_key      = f"backups/trading_bot_{timestamp}.db"

            self.client.upload_file(DB_PATH, AWS_BUCKET, s3_key)

            size_kb = os.path.getsize(DB_PATH) / 1024
            logger.info(f"✅ S3 Backup επιτυχής → {s3_key} ({size_kb:.1f} KB)")

            # Καθάρισε παλιά backups
            self._cleanup_old_backups()
            return True

        except Exception as e:
            logger.error(f"❌ S3 Backup αποτυχία: {e}")
            return False

    def restore_latest(self) -> bool:
        """
        Κατεβάζει το πιο πρόσφατο backup από S3.
        Χρησιμοποιείται αν χαθεί η local database.
        """
        if not self.enabled:
            return False

        try:
            response = self.client.list_objects_v2(
                Bucket = AWS_BUCKET,
                Prefix = "backups/trading_bot_"
            )

            if "Contents" not in response:
                logger.warning("Δεν βρέθηκαν backups στο S3")
                return False

            # Βρες το πιο πρόσφατο
            latest = max(response["Contents"], key=lambda x: x["LastModified"])
            s3_key = latest["Key"]

            self.client.download_file(AWS_BUCKET, s3_key, DB_PATH)
            logger.info(f"✅ Restore από S3: {s3_key}")
            return True

        except Exception as e:
            logger.error(f"❌ S3 Restore αποτυχία: {e}")
            return False

    def _cleanup_old_backups(self):
        """Διαγράφει backups παλαιότερα από 7 μέρες."""
        try:
            cutoff = datetime.now() - timedelta(days=KEEP_DAYS)

            response = self.client.list_objects_v2(
                Bucket = AWS_BUCKET,
                Prefix = "backups/"
            )

            if "Contents" not in response:
                return

            deleted = 0
            for obj in response["Contents"]:
                if obj["LastModified"].replace(tzinfo=None) < cutoff:
                    self.client.delete_object(Bucket=AWS_BUCKET, Key=obj["Key"])
                    deleted += 1

            if deleted > 0:
                logger.info(f"🗑️  Διαγράφηκαν {deleted} παλιά backups")

        except Exception as e:
            logger.error(f"Cleanup error: {e}")

    def list_backups(self):
        """Εμφανίζει όλα τα backups στο S3."""
        if not self.enabled:
            return []

        try:
            response = self.client.list_objects_v2(
                Bucket = AWS_BUCKET,
                Prefix = "backups/"
            )

            if "Contents" not in response:
                return []

            backups = []
            for obj in sorted(response["Contents"], key=lambda x: x["LastModified"], reverse=True):
                backups.append({
                    "key":      obj["Key"],
                    "size_kb":  round(obj["Size"] / 1024, 1),
                    "date":     obj["LastModified"].strftime("%Y-%m-%d %H:%M"),
                })

            return backups

        except Exception as e:
            logger.error(f"List backups error: {e}")
            return []
