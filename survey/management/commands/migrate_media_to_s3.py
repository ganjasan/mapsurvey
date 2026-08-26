"""Copy the media tree off the local disk into the S3 bucket.

Run once, from a shell on the service that mounts the disk, BEFORE `USE_S3` is
switched on. Deliberately reads its bucket configuration straight from the
environment rather than from settings: while `USE_S3` is still off the S3
settings do not exist, and that is exactly the window this command runs in.

There is no `aws` CLI in the image, so this is the migration path — boto3 comes
in with django-storages.

Usage, from the Render shell on the web service:

  export AWS_STORAGE_BUCKET_NAME=mapsurvey-media-prod
  export AWS_S3_REGION_NAME=ap-southeast-2
  export AWS_ACCESS_KEY_ID=... AWS_SECRET_ACCESS_KEY=...
  python manage.py migrate_media_to_s3 --dry-run   # see what would move
  python manage.py migrate_media_to_s3             # copy
  python manage.py migrate_media_to_s3 --verify    # count and compare sizes

Safe to re-run: an object that already exists with the same size is skipped, and
nothing on the disk is ever modified or deleted. The disk stays the backup until
someone removes the `disk:` block from render.yaml.
"""

import mimetypes
import os

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

DEFAULT_PREFIX = 'media'


def iter_local_files(root):
    """Yield (absolute_path, relative_path) for every file under root."""
    for dirpath, _dirnames, filenames in os.walk(root):
        for filename in filenames:
            absolute = os.path.join(dirpath, filename)
            yield absolute, os.path.relpath(absolute, root)


class Command(BaseCommand):
    help = 'Copy MEDIA_ROOT into the S3 media bucket. Non-destructive and re-runnable.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                            help='Report what would be copied without writing anything.')
        parser.add_argument('--verify', action='store_true',
                            help='Compare disk and bucket without copying.')
        parser.add_argument('--prefix', default=os.getenv('MEDIA_S3_PREFIX', DEFAULT_PREFIX),
                            help=f'Key prefix to copy into (default: {DEFAULT_PREFIX}).')
        parser.add_argument('--media-root', default=None,
                            help='Override the source directory (defaults to MEDIA_ROOT).')

    def handle(self, *args, **options):
        root = options['media_root'] or getattr(settings, 'MEDIA_ROOT', None)
        if not root or not os.path.isdir(root):
            raise CommandError(f'Media root {root!r} does not exist — is this the service with the disk?')

        bucket_name = os.getenv('AWS_STORAGE_BUCKET_NAME')
        region = os.getenv('AWS_S3_REGION_NAME')
        if not bucket_name or not region:
            raise CommandError(
                'AWS_STORAGE_BUCKET_NAME and AWS_S3_REGION_NAME must be set. '
                'They are read from the environment, not from settings, because this '
                'command runs while USE_S3 is still off.'
            )

        prefix = options['prefix'].strip('/')

        import boto3
        from botocore.exceptions import ClientError

        client = boto3.client(
            's3',
            region_name=region,
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
            config=boto3.session.Config(signature_version='s3v4'),
        )

        local = list(iter_local_files(root))
        if not local:
            self.stdout.write(f'Nothing under {root} — no media to copy.')
            return

        total_bytes = sum(os.path.getsize(a) for a, _ in local)
        self.stdout.write(f'{len(local)} files, {total_bytes} bytes under {root}')
        self.stdout.write(f'Target: s3://{bucket_name}/{prefix}/ ({region})\n')

        copied = skipped = mismatched = 0
        for absolute, relative in sorted(local, key=lambda pair: pair[1]):
            key = f'{prefix}/{relative}'.replace(os.sep, '/')
            size = os.path.getsize(absolute)

            remote_size = None
            try:
                remote_size = client.head_object(Bucket=bucket_name, Key=key)['ContentLength']
            except ClientError as exc:
                if exc.response['Error']['Code'] not in ('404', 'NoSuchKey', '403'):
                    raise

            if remote_size is not None:
                if remote_size == size:
                    skipped += 1
                    continue
                # Same key, different bytes: report it, never silently overwrite.
                mismatched += 1
                self.stdout.write(self.style.WARNING(
                    f'DIFFERS {key} (disk {size} bytes, bucket {remote_size} bytes) — left untouched'
                ))
                continue

            if options['verify']:
                self.stdout.write(self.style.WARNING(f'MISSING {key}'))
                continue
            if options['dry_run']:
                self.stdout.write(f'would copy {key} ({size} bytes)')
                continue

            content_type, _ = mimetypes.guess_type(absolute)
            extra = {'ContentType': content_type} if content_type else {}
            # No ACL: the bucket is BucketOwnerEnforced and public read comes
            # from its policy. Sending one would fail the upload.
            client.upload_file(absolute, bucket_name, key, ExtraArgs=extra)
            copied += 1
            self.stdout.write(f'copied {key} ({size} bytes)')

        self.stdout.write('')
        if options['verify']:
            self.stdout.write(
                self.style.SUCCESS(f'Verify: {skipped}/{len(local)} present with matching size, '
                                   f'{mismatched} differing.')
            )
        elif options['dry_run']:
            self.stdout.write('Dry run — nothing was written.')
        else:
            self.stdout.write(self.style.SUCCESS(
                f'Copied {copied}, already present {skipped}, differing {mismatched}. '
                f'The disk was not modified.'
            ))
