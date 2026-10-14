"""Report surveys whose draft publish dropped fields the draft copy never carried (#329).

Until change `draft-copy-keeps-fields`, `clone_survey_for_draft` lost `SurveySection.layout`,
`next_label`, `hidden_layers`, `visibility_rule`, the translations' `next_label` and every
`Question.visibility_rule`; publishing then wrote the stripped draft over the live survey. The
previous structure survives as the archived version, so the loss is visible by comparing the
newest archived version with the canonical, lineage by lineage (section and question codes are
stable across versions).

Read-only. Nothing is restored: the owner decides, and restores by hand or by restoring the
version as a new draft (which keeps the fields since the fix).
"""
from django.core.management.base import BaseCommand

from survey.versioning import find_draft_field_loss


class Command(BaseCommand):
    help = "List surveys where a draft publish stripped rules, layout, labels or hidden layers (read-only)"

    def handle(self, *args, **options):
        reports = find_draft_field_loss()
        if not reports:
            self.stdout.write("No survey lost fields on a draft publish.")
            return
        for report in reports:
            survey = report['survey']
            self.stdout.write(
                f"{survey.uuid}  {survey.name!r}  org={survey.organization.name!r}  "
                f"v{report['archived_version']} -> v{survey.version_number}"
            )
            for line in report['losses']:
                self.stdout.write(f"    {line}")
        self.stdout.write(f"{len(reports)} survey(s) affected.")
