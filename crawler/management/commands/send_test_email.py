from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

from crawler.services.email_digest import send_weekly_digest


class Command(BaseCommand):
    help = "Send digest email manually for testing. Uses env/settings recipient automatically."

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=getattr(settings, "CRAWLER_RECENCY_DAYS", 10),
            help="Recency window in days (default: settings.CRAWLER_RECENCY_DAYS or 10)",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=40,
            help="Max number of items to send (default: 40)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Do not send; just print how many would be sent.",
        )

    def handle(self, *args, **options):
        days = options["days"]
        limit = options["limit"]
        dry_run = options["dry_run"]

        # Use settings / env email automatically
        recipient = getattr(settings, "DIGEST_TO_EMAIL", None)
        if not recipient:
            raise CommandError(
                "DIGEST_TO_EMAIL is not set in settings.py or environment."
            )

        self.stdout.write(f"[EMAIL] Using recipient from settings: {recipient}")

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"[DRY RUN] Would send digest to {recipient} (days={days}, limit={limit})"
                )
            )
            return

        try:
            n = send_weekly_digest(days=days, limit=limit)
        except Exception as e:
            raise CommandError(f"Email send failed: {e}")

        self.stdout.write(
            self.style.SUCCESS(f"Sent digest successfully. items_sent={n}")
        )
