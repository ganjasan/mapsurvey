"""Tests for the `media-storage` capability (openspec/specs/media-storage/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import SimpleTestCase, override_settings
from unittest import mock
import os
from io import StringIO
from django.core.management import call_command


class MediaStorageConfigurationTest(SimpleTestCase):
    """The USE_S3 branch of settings, and the two storage tiers it selects.

    These are the failures that cost a production incident rather than a red
    test: an ACL on a bucket that forbids ACLs, a region-less domain that
    redirects, static silently following media to S3, and — the expensive one —
    a respondent's photo handed out as a permanent public link.
    """

    def test_local_default_storage_is_the_filesystem(self):
        """
        GIVEN USE_S3 is unset, as it is locally and in the test suite
        WHEN the default file storage is resolved
        THEN it is Django's filesystem storage and media is served locally
        """
        from django.conf import settings as s
        from django.core.files.storage import FileSystemStorage, default_storage

        self.assertFalse(s.USE_S3)
        self.assertIsInstance(default_storage, FileSystemStorage)
        self.assertEqual(s.MEDIA_URL, '/mediafiles/')

    def test_static_stays_on_whitenoise(self):
        """
        GIVEN static files must never follow media to object storage
        WHEN the staticfiles backend is read
        THEN it is WhiteNoise's manifest storage
        """
        from django.conf import settings as s

        self.assertEqual(
            s.STORAGES['staticfiles']['BACKEND'],
            'whitenoise.storage.CompressedManifestStaticFilesStorage',
        )

    def test_legacy_storage_settings_are_gone(self):
        """
        GIVEN Django 4.2 deprecates DEFAULT_FILE_STORAGE and 5.1 removes it
        WHEN the project's own settings module is inspected
        THEN it defines neither legacy name, only STORAGES

        Asserted against the module rather than `django.conf.settings`, because
        Django's own global_settings still defines both names — the object
        always has them, so only the project namespace can tell us anything.
        """
        import mapsurvey.settings as project_settings

        self.assertFalse(hasattr(project_settings, 'DEFAULT_FILE_STORAGE'))
        self.assertFalse(hasattr(project_settings, 'STATICFILES_STORAGE'))
        self.assertIn('default', project_settings.STORAGES)


class MediaPrefixTest(SimpleTestCase):
    """Namespace-to-prefix mapping — what keeps a preview off production keys."""

    def test_production_keeps_the_bare_prefixes(self):
        """
        GIVEN production runs with no namespace
        WHEN the media locations are computed
        THEN they are the bare prefixes the database paths already resolve under
        """
        from mapsurvey.media_prefixes import media_locations

        self.assertEqual(media_locations(''), ('media', 'uploads'))
        self.assertEqual(media_locations(None), ('media', 'uploads'))

    def test_a_namespace_moves_both_tiers(self):
        """
        GIVEN a PR preview sets a namespace
        WHEN the media locations are computed
        THEN both the public and the private prefix sit under it
        """
        from mapsurvey.media_prefixes import media_locations

        public, private = media_locations('previews/mapsurvey-pr-123')
        self.assertEqual(public, 'previews/mapsurvey-pr-123/media')
        self.assertEqual(private, 'previews/mapsurvey-pr-123/uploads')

    def test_stray_slashes_do_not_produce_empty_key_segments(self):
        """
        GIVEN an operator sets the namespace with leading or trailing slashes
        WHEN the media locations are computed
        THEN the prefixes contain no doubled or dangling separator
        """
        from mapsurvey.media_prefixes import media_locations

        self.assertEqual(
            media_locations('/previews/pr-1/'),
            ('previews/pr-1/media', 'previews/pr-1/uploads'),
        )


@override_settings(
    AWS_STORAGE_BUCKET_NAME='mapsurvey-media-test',
    AWS_S3_REGION_NAME='ap-southeast-2',
    AWS_S3_CUSTOM_DOMAIN='mapsurvey-media-test.s3.ap-southeast-2.amazonaws.com',
    AWS_ACCESS_KEY_ID='testing-key-id',
    AWS_SECRET_ACCESS_KEY='testing-secret',
    AWS_DEFAULT_ACL=None,
    AWS_QUERYSTRING_EXPIRE=900,
    AWS_S3_SIGNATURE_VERSION='s3v4',
    AWS_S3_ADDRESSING_STYLE='virtual',
    PUBLIC_MEDIA_LOCATION='media',
    PRIVATE_MEDIA_LOCATION='uploads',
)
class MediaStorageTierTest(SimpleTestCase):
    """Public artwork versus private submissions. No network: signing is local."""

    def test_public_tier_serves_unsigned_regional_urls(self):
        """
        GIVEN creator artwork is public and should cache well
        WHEN a URL is built for a stored cover image
        THEN it uses the Region-qualified host and carries no signature
        """
        from survey.storage_backends import PublicMediaStorage

        url = PublicMediaStorage().url('covers/cover.png')

        self.assertTrue(
            url.startswith('https://mapsurvey-media-test.s3.ap-southeast-2.amazonaws.com/media/'),
            url,
        )
        self.assertNotIn('X-Amz-Signature', url)

    def test_public_tier_never_sends_an_object_acl(self):
        """
        GIVEN the bucket is BucketOwnerEnforced, so any ACL fails the upload
        WHEN the public storage is configured
        THEN it carries no default ACL
        """
        from survey.storage_backends import PublicMediaStorage

        self.assertIsNone(PublicMediaStorage().default_acl)

    def test_private_tier_signs_its_urls(self):
        """
        GIVEN respondent submissions must not be fetchable by URL alone
        WHEN a URL is built for a stored submission
        THEN it is signed and expires
        """
        from survey.storage_backends import PrivateMediaStorage

        url = PrivateMediaStorage().url('answers/photo.jpg')

        # SigV4, not the deprecated SigV2 scheme boto3 falls back to when the
        # signature version is left unset.
        self.assertIn('X-Amz-Signature', url)
        self.assertIn('X-Amz-Expires', url)
        self.assertNotIn('AWSAccessKeyId', url)
        # And against the bucket's own Region, not the global endpoint that
        # answers 307.
        self.assertIn('s3.ap-southeast-2.amazonaws.com', url)
        self.assertIn('/uploads/answers/photo.jpg', url)

    def test_private_tier_refuses_a_custom_domain(self):
        """
        GIVEN S3Boto3Storage.url() skips signing entirely when a custom domain is set
        WHEN the private storage is configured
        THEN it has no custom domain, so a signature is always produced

        This is the guard on the expensive mistake: a custom domain here would
        turn every respondent's photo into a permanent public link.
        """
        from survey.storage_backends import PrivateMediaStorage

        self.assertIsNone(PrivateMediaStorage().custom_domain)

    def test_the_two_tiers_never_share_a_prefix(self):
        """
        GIVEN the bucket policy grants anonymous read to the public prefix only
        WHEN both storages report where they write
        THEN the private prefix is not inside the public one
        """
        from survey.storage_backends import PrivateMediaStorage, PublicMediaStorage

        public = PublicMediaStorage().location
        private = PrivateMediaStorage().location

        self.assertNotEqual(public, private)
        self.assertFalse(private.startswith(f'{public}/'))


class MediaNamespaceFromEnvTest(SimpleTestCase):
    """Which prefix an environment claims — the guard on previews vs production."""

    def test_production_claims_no_namespace(self):
        """
        GIVEN a production environment with no media namespace set
        WHEN the namespace is derived
        THEN it is empty, so keys stay where the database paths resolve
        """
        from mapsurvey.media_prefixes import namespace_from_env

        self.assertEqual(namespace_from_env({}), '')

    def test_a_preview_names_itself_after_its_service(self):
        """
        GIVEN Render marks a pull-request environment and names the service
        WHEN the namespace is derived
        THEN it is scoped under previews/ by that service name
        """
        from mapsurvey.media_prefixes import namespace_from_env

        ns = namespace_from_env({
            'IS_PULL_REQUEST': 'true',
            'RENDER_SERVICE_NAME': 'mapsurvey-pr-123',
        })
        self.assertEqual(ns, 'previews/mapsurvey-pr-123')

    def test_a_nameless_preview_still_stays_out_of_production(self):
        """
        GIVEN a pull-request environment whose service name is missing
        WHEN the namespace is derived
        THEN it is still under previews/, never production's prefix

        The failure this prevents: a preview writing into media/ would put test
        files in front of real respondents and could overwrite a creator's cover.
        """
        from mapsurvey.media_prefixes import namespace_from_env

        self.assertEqual(namespace_from_env({'IS_PULL_REQUEST': 'true'}), 'previews/unnamed')

    def test_an_explicit_namespace_wins(self):
        """
        GIVEN an operator pins the namespace explicitly
        WHEN the namespace is derived
        THEN the explicit value is used, even on a preview and even when empty
        """
        from mapsurvey.media_prefixes import namespace_from_env

        self.assertEqual(
            namespace_from_env({'MEDIA_S3_NAMESPACE': 'staging', 'IS_PULL_REQUEST': 'true'}),
            'staging',
        )
        self.assertEqual(
            namespace_from_env({'MEDIA_S3_NAMESPACE': '', 'IS_PULL_REQUEST': 'true'}),
            '',
        )


@override_settings(
    USE_S3=True,
    AWS_STORAGE_BUCKET_NAME='mapsurvey-media-test',
    AWS_S3_REGION_NAME='ap-southeast-2',
    AWS_ACCESS_KEY_ID='testing-key-id',
    AWS_SECRET_ACCESS_KEY='testing-secret',
)
class ReclaimPreviewMediaTest(SimpleTestCase):
    """Reclaiming media from previews that no longer exist.

    Render has no teardown hook, so this reconciles against its API. The
    dangerous direction is deleting media that is still in use, which is why an
    untrustworthy service listing must delete nothing at all.
    """

    def _bucket(self, prefixes, objects_per_prefix=2):
        """A boto3 Bucket double that reports the given preview prefixes."""
        bucket = mock.MagicMock()
        bucket.name = 'mapsurvey-media-test'
        paginator = mock.MagicMock()
        paginator.paginate.return_value = [
            {'CommonPrefixes': [{'Prefix': p} for p in prefixes]}
        ]
        bucket.meta.client.get_paginator.return_value = paginator
        bucket.objects.filter.return_value = mock.MagicMock(
            __iter__=lambda self: iter([mock.MagicMock()] * objects_per_prefix),
            delete=mock.MagicMock(),
        )
        return bucket

    def _run(self, bucket, *args):
        from django.core.management import call_command
        from io import StringIO

        out = StringIO()
        with mock.patch('boto3.resource') as resource:
            resource.return_value.Bucket.return_value = bucket
            call_command('reclaim_preview_media', *args, stdout=out)
        return out.getvalue()

    def test_missing_token_disables_reclamation_without_failing(self):
        """
        GIVEN RENDER_API_KEY is not configured
        WHEN the command runs
        THEN it reports that reclamation is disabled and deletes nothing
        """
        import os

        bucket = self._bucket(['previews/mapsurvey-pr-1/'])
        with mock.patch.dict('os.environ', {}, clear=False):
            os.environ.pop('RENDER_API_KEY', None)
            output = self._run(bucket, '--delete')

        self.assertIn('reclamation disabled', output)
        bucket.objects.filter.return_value.delete.assert_not_called()

    def test_an_untrustworthy_service_listing_deletes_nothing(self):
        """
        GIVEN the Render API cannot be listed
        WHEN the command runs with --delete
        THEN it fails loudly and deletes nothing

        A partial listing would make live previews look dead, so the only safe
        response to an unreadable listing is to touch nothing.
        """
        from django.core.management.base import CommandError
        from survey.management.commands.reclaim_preview_media import RenderUnavailable

        bucket = self._bucket(['previews/mapsurvey-pr-1/'])
        with mock.patch.dict('os.environ', {'RENDER_API_KEY': 'tok'}), \
             mock.patch(
                 'survey.management.commands.reclaim_preview_media.live_service_names',
                 side_effect=RenderUnavailable('boom'),
             ):
            with self.assertRaises(CommandError):
                self._run(bucket, '--delete')

        bucket.objects.filter.return_value.delete.assert_not_called()

    def test_a_live_preview_is_left_alone(self):
        """
        GIVEN a preview whose Render service still exists
        WHEN the command runs with --delete
        THEN its objects are retained
        """
        bucket = self._bucket(['previews/mapsurvey-pr-1/'])
        with mock.patch.dict('os.environ', {'RENDER_API_KEY': 'tok'}), \
             mock.patch(
                 'survey.management.commands.reclaim_preview_media.live_service_names',
                 return_value={'mapsurvey-pr-1'},
             ):
            output = self._run(bucket, '--delete')

        self.assertIn('keep', output)
        bucket.objects.filter.return_value.delete.assert_not_called()

    def test_a_dead_preview_is_reclaimed(self):
        """
        GIVEN a preview whose Render service is gone
        WHEN the command runs with --delete
        THEN its objects are deleted
        """
        bucket = self._bucket(['previews/mapsurvey-pr-1/'])
        with mock.patch.dict('os.environ', {'RENDER_API_KEY': 'tok'}), \
             mock.patch(
                 'survey.management.commands.reclaim_preview_media.live_service_names',
                 return_value={'mapsurvey'},
             ):
            output = self._run(bucket, '--delete')

        self.assertIn('deleted', output)
        bucket.objects.filter.return_value.delete.assert_called()

    def test_dry_run_is_the_default(self):
        """
        GIVEN the command is run without --delete
        WHEN a dead preview's prefix is found
        THEN it is only reported, never removed
        """
        bucket = self._bucket(['previews/mapsurvey-pr-1/'])
        with mock.patch.dict('os.environ', {'RENDER_API_KEY': 'tok'}), \
             mock.patch(
                 'survey.management.commands.reclaim_preview_media.live_service_names',
                 return_value={'mapsurvey'},
             ):
            output = self._run(bucket)

        self.assertIn('would delete', output)
        bucket.objects.filter.return_value.delete.assert_not_called()

    def test_reclamation_is_skipped_entirely_without_s3(self):
        """
        GIVEN USE_S3 is off
        WHEN the command runs
        THEN it does nothing at all — there is no object storage to reclaim
        """
        from django.core.management import call_command
        from io import StringIO

        out = StringIO()
        with override_settings(USE_S3=False):
            call_command('reclaim_preview_media', '--delete', stdout=out)

        self.assertIn('no object storage', out.getvalue())
