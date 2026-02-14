"""
Data migration: create default "Mapsurvey" organization, assign all existing
users as owners, assign all unassigned surveys, create SurveyCollaborator
owner entries for existing surveys.
"""
from django.db import migrations
from django.utils.text import slugify


def populate_default_org(apps, schema_editor):
    Organization = apps.get_model('survey', 'Organization')
    Membership = apps.get_model('survey', 'Membership')
    SurveyHeader = apps.get_model('survey', 'SurveyHeader')
    SurveyCollaborator = apps.get_model('survey', 'SurveyCollaborator')
    User = apps.get_model('auth', 'User')

    # 1. Create default org (or get existing)
    default_org, created = Organization.objects.get_or_create(
        slug='mapsurvey',
        defaults={'name': 'Mapsurvey'},
    )

    # 2. Populate slugs for any existing orgs that don't have one
    for org in Organization.objects.filter(slug__isnull=True):
        base_slug = slugify(org.name)[:100] or 'org'
        slug = base_slug
        counter = 2
        while Organization.objects.filter(slug=slug).exclude(pk=org.pk).exists():
            suffix = f'-{counter}'
            slug = base_slug[:100 - len(suffix)] + suffix
            counter += 1
        org.slug = slug
        org.save(update_fields=['slug'])

    # Also handle empty-string slugs
    for org in Organization.objects.filter(slug=''):
        base_slug = slugify(org.name)[:100] or 'org'
        slug = base_slug
        counter = 2
        while Organization.objects.filter(slug=slug).exclude(pk=org.pk).exists():
            suffix = f'-{counter}'
            slug = base_slug[:100 - len(suffix)] + suffix
            counter += 1
        org.slug = slug
        org.save(update_fields=['slug'])

    # 3. Assign all existing users as owners of default org
    for user in User.objects.all():
        Membership.objects.get_or_create(
            user=user,
            organization=default_org,
            defaults={'role': 'owner'},
        )

    # 4. Assign all surveys without org to the default org
    SurveyHeader.objects.filter(organization__isnull=True).update(organization=default_org)

    # 5. Create SurveyCollaborator owner entries for existing surveys
    first_user = User.objects.order_by('id').first()
    if first_user:
        for survey in SurveyHeader.objects.all():
            # Use created_by if set, otherwise first user
            owner_user = survey.created_by or first_user
            SurveyCollaborator.objects.get_or_create(
                user=owner_user,
                survey=survey,
                defaults={'role': 'owner'},
            )


def reverse_populate(apps, schema_editor):
    # Data migration reverse: we don't delete the default org or memberships
    # because that could cause data loss. The schema reverse will drop the tables.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('survey', '0012_add_org_membership_access_control'),
    ]

    operations = [
        migrations.RunPython(populate_default_org, reverse_populate),
    ]
