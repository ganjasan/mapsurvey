"""Delete media belonging to PR previews that no longer exist.

Preview environments write under `previews/<service>/`, and Render offers no
teardown hook — nothing tells us the moment a preview is destroyed. So this
reconciles instead: list the preview prefixes in the bucket, ask Render which
services still exist, and delete the objects of the ones that do not. Run on a
schedule, it converges within one period of a pull request closing.

Usage:
  python manage.py reclaim_preview_media            # dry run: report only
  python manage.py reclaim_preview_media --delete   # actually delete

Deleting requires the explicit flag. The failure mode this guards against is
deleting live preview media — or worse, production media — because the service
listing came back wrong, so an incomplete or failed listing deletes nothing.
"""

import os

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

RENDER_API_SERVICES = 'https://api.render.com/v1/services'
PREVIEW_ROOT = 'previews/'


class RenderUnavailable(Exception):
    """The service listing could not be trusted, so nothing may be deleted."""


def live_service_names(api_key, timeout=30):
    """Return the set of service names Render currently knows about.

    Raises RenderUnavailable rather than returning a partial set: a truncated
    listing would make live previews look dead and get their media deleted.
    """
    import requests

    names = set()
    cursor = None
    while True:
        params = {'limit': 100, 'includePreviews': 'true'}
        if cursor:
            params['cursor'] = cursor
        try:
            response = requests.get(
                RENDER_API_SERVICES,
                params=params,
                headers={'Authorization': f'Bearer {api_key}', 'Accept': 'application/json'},
                timeout=timeout,
            )
            response.raise_for_status()
            page = response.json()
        except Exception as exc:  # network, auth, malformed body — all untrustworthy
            raise RenderUnavailable(str(exc)) from exc

        if not page:
            break
        for entry in page:
            service = entry.get('service') or {}
            name = service.get('name')
            if name:
                names.add(name)
            cursor = entry.get('cursor') or cursor
        if len(page) < 100:
            break

    if not names:
        # Zero services means the token is scoped to nothing, or the shape of
        # the response changed. Either way it is not evidence that every
        # preview is gone.
        raise RenderUnavailable('Render returned no services')
    return names


def preview_prefixes(bucket):
    """Yield the `previews/<service>/` prefixes that currently hold objects."""
    paginator = bucket.meta.client.get_paginator('list_objects_v2')
    for page in paginator.paginate(Bucket=bucket.name, Prefix=PREVIEW_ROOT, Delimiter='/'):
        for entry in page.get('CommonPrefixes', []):
            yield entry['Prefix']


class Command(BaseCommand):
    help = 'Delete media left behind by PR previews whose Render service is gone.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--delete',
            action='store_true',
            help='Actually delete. Without it the command only reports what it would remove.',
        )

    def handle(self, *args, **options):
        if not getattr(settings, 'USE_S3', False):
            self.stdout.write('USE_S3 is off — no object storage to reclaim. Nothing to do.')
            return

        api_key = os.getenv('RENDER_API_KEY')
        if not api_key:
            # Not configured is not breakage: the bucket simply keeps preview
            # objects until someone wires the token up.
            self.stdout.write('RENDER_API_KEY is not set — reclamation disabled, nothing deleted.')
            return

        import boto3

        s3 = boto3.resource(
            's3',
            region_name=settings.AWS_S3_REGION_NAME,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        )
        bucket = s3.Bucket(settings.AWS_STORAGE_BUCKET_NAME)

        prefixes = list(preview_prefixes(bucket))
        if not prefixes:
            self.stdout.write('No preview prefixes in the bucket.')
            return

        try:
            live = live_service_names(api_key)
        except RenderUnavailable as exc:
            raise CommandError(f'Could not list Render services ({exc}) — deleted nothing.')

        reclaimed = 0
        for prefix in prefixes:
            service = prefix[len(PREVIEW_ROOT):].rstrip('/')
            if service in live:
                self.stdout.write(f'keep   {prefix} (service still exists)')
                continue

            objects = list(bucket.objects.filter(Prefix=prefix))
            if not options['delete']:
                self.stdout.write(f'would delete {prefix} ({len(objects)} objects)')
                continue

            bucket.objects.filter(Prefix=prefix).delete()
            reclaimed += len(objects)
            self.stdout.write(self.style.SUCCESS(f'deleted {prefix} ({len(objects)} objects)'))

        if options['delete']:
            self.stdout.write(self.style.SUCCESS(f'Reclaimed {reclaimed} objects.'))
        else:
            self.stdout.write('Dry run — pass --delete to remove the objects listed above.')
