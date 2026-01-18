from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.db.models import QuerySet

from crawler.models import ReportItem


class Command(BaseCommand):
    help = "Unmark sent items (set sent_at=NULL) so they can be emailed again."

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=None,
            help="Only unmark items with published_at >= now - days (optional).",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Maximum number of items to unmark (optional).",
        )
        parser.add_argument(
            "--all",
            action="store_true",
            help="Unmark ALL items that have sent_at set (ignores --days).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Do not write changes; only print how many would be unmarked.",
        )

    def handle(self, *args, **options):
        days = options["days"]
        limit = options["limit"]
        do_all = options["all"]
        dry_run = options["dry_run"]

        if not do_all and days is None:
            raise CommandError("You must pass either --all or --days N")

        qs: QuerySet = ReportItem.objects.filter(sent_at__isnull=False)

        if not do_all:
            cutoff = timezone.now() - timedelta(days=days)
            qs = qs.filter(published_at__isnull=False, published_at__gte=cutoff)

        qs = qs.order_by("-sent_at", "-id")

        if limit:
            ids = list(qs.values_list("id", flat=True)[:limit])
            qs = ReportItem.objects.filter(id__in=ids)

        count = qs.count()

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"[DRY RUN] Would unmark sent_at for {count} item(s)."
                )
            )
            return

        updated = qs.update(sent_at=None)
        self.stdout.write(
            self.style.SUCCESS(f"Unmarked sent_at for {updated} item(s).")
        )
