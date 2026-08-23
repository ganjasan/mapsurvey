"""Backfill draft public results pages for already-published surveys.

One-off companion to the publish-time scaffold (survey.public_results
.scaffold_page): surveys that reached published/closed before the feature
shipped get the same draft. Safe to re-run — scaffolded pages are skipped.
See openspec/changes/auto-draft-public-results/design.md.
"""
from django.core.management.base import BaseCommand

from survey.models import SurveyHeader, PublicResultsPage
from survey.public_results import scaffold_page


class Command(BaseCommand):
    help = "Create draft public results pages for published surveys that have none"

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='List surveys that would be scaffolded without writing anything',
        )

    def handle(self, *args, **options):
        candidates = (
            SurveyHeader.objects
            .filter(status__in=('published', 'closed'),
                    is_canonical=True, deleted_at__isnull=True)
            .order_by('id')
        )
        seen = 0
        for survey in candidates:
            page = PublicResultsPage.objects.filter(survey=survey).first()
            if page is not None and (page.scaffolded_at is not None or page.blocks.exists()):
                continue
            if options['dry_run']:
                self.stdout.write(f"would scaffold: {survey.name} ({survey.uuid})")
            else:
                page = scaffold_page(survey)
                self.stdout.write(
                    f"scaffolded: {survey.name} ({survey.uuid}) -> "
                    f"{page.blocks.count()} block(s), /r/{page.slug}/"
                )
            seen += 1
        if seen == 0:
            self.stdout.write("Nothing to scaffold")
