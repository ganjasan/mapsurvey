"""Rejoin the two 0065 leaves.

`0065_pro_interest` (PR #139) and `0065_repair_organization_slugs` (PR #143)
were written in parallel worktrees against different views of master and both
landed, leaving two leaf nodes: `migrate` then refuses to run at all, which
failed the pre-deploy step and blocked the release. No operations -- the two
branches touch different models and neither needs replaying.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('survey', '0065_pro_interest'),
        ('survey', '0065_repair_organization_slugs'),
    ]

    operations = [
    ]
