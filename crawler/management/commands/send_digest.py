from django.core.management.base import BaseCommand
from django.conf import settings

from crawler.services.email_digest import send_weekly_digest


class Command(BaseCommand):
    help = "Send digest immediately (same logic as weekly_run), without crawling/validation."

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=None,
            help="Recency window in days (default: settings.CRAWLER_RECENCY_DAYS or 10).",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=40,
            help="Max number of items to send (default: 40).",
        )

    def handle(self, *args, **options):
        days = options.get("days")
        limit = options.get("limit")

        if days is None:
            days = getattr(settings, "CRAWLER_RECENCY_DAYS", 10)

        self.stdout.write(f"[SEND_DIGEST] start days={days} limit={limit}")
        n = send_weekly_digest(days=days, limit=limit)
        self.stdout.write(self.style.SUCCESS(f"[SEND_DIGEST] done items_sent={n}"))
