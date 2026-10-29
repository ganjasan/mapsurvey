"""Give every existing account an EmailVerification row (change login-grace-period, #487).

Active accounts are confirmed. Accounts that registered and never activated
(`is_active=False`, never signed in) become active and unconfirmed, their grace
period long over: their next sign-in names the reason and sends a link.
Banned accounts stay banned. The rule is `survey.email_verification.classify`;
`manage.py sync_email_verification` re-runs it for rows created by the old
instance during the deploy window.
"""

from django.db import migrations


def forwards(apps, schema_editor):
    from survey.email_verification import sync_accounts

    sync_accounts(
        apps.get_model('auth', 'User'),
        apps.get_model('survey', 'EmailVerification'),
        apps.get_model('survey', 'ContentReview'),
    )


class Migration(migrations.Migration):

    dependencies = [
        ('survey', '0110_email_verification'),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
