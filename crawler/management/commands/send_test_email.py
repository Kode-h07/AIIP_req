import os
from django.core.management.base import BaseCommand, CommandError

from crawler.services.email_digest import send_raw_email


class Command(BaseCommand):
    help = "Send a test email using .env variables DIGEST_TO_EMAIL / DIGEST_FROM_EMAIL"

    def handle(self, *args, **options):
        to_email = (os.getenv("DIGEST_TO_EMAIL") or "").strip()
        from_email = (os.getenv("DIGEST_FROM_EMAIL") or os.getenv("EMAIL_HOST_USER") or "").strip()

        if not to_email:
            raise CommandError("DIGEST_TO_EMAIL is not set in .env")
        if not from_email:
            raise CommandError("DIGEST_FROM_EMAIL (or EMAIL_HOST_USER) is not set in .env")

        subject = "[TEST] AI × IP Digest Email Test"
        body = "This is a test email. If you received it, SMTP settings are working."

        try:
            send_raw_email(subject=subject, body=body, to_email=to_email, from_email=from_email)
        except Exception as e:
            raise CommandError(f"Email send failed: {e}")

        self.stdout.write(self.style.SUCCESS(f"Test email sent to {to_email}"))
