from django.core.management.base import BaseCommand
from django.conf import settings

from crawler.services.email_digest import send_weekly_digest


class Command(BaseCommand):
    help = "Run weekly pipeline: crawl seeds, crawl queries, validate/prune, then email digest."

    def handle(self, *args, **options):
        # 1) Crawl seeds
        # self.stdout.write("[WEEKLY] crawl_seeds start")
        # from crawler.management.commands.crawl_seeds import Command as SeedCommand

        # SeedCommand().handle()
        # self.stdout.write("[WEEKLY] crawl_seeds done")

        # 2) Crawl queries
        self.stdout.write("[WEEKLY] crawl_queries start")
        from crawler.management.commands.crawl_queries import Command as QueryCommand

        QueryCommand().handle()
        self.stdout.write("[WEEKLY] crawl_queries done")

        # 3) Validate + prune (Gemini + OpenAI + strict recency)
        self.stdout.write("[WEEKLY] validate_and_prune start")
        from crawler.management.commands.validate_and_prune import (
            Command as ValidateCommand,
        )

        ValidateCommand().handle()
        self.stdout.write("[WEEKLY] validate_and_prune done")

        # 4) Send digest (only verified & recent should remain)
        days = getattr(settings, "CRAWLER_RECENCY_DAYS", 10)
        self.stdout.write("[WEEKLY] send_digest start")
        n = send_weekly_digest(days=days, limit=40)
        self.stdout.write(
            self.style.SUCCESS(f"[WEEKLY] send_digest done: items_sent={n}")
        )
