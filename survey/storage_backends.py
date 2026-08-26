from django.conf import settings
from storages.backends.s3boto3 import S3Boto3Storage


class PublicMediaStorage(S3Boto3Storage):
    """Creator-authored artwork: survey covers, question images, story covers.

    Anonymously readable, because it is already on display on every survey and
    public results page. Read access comes from the bucket policy, never from an
    object ACL — the bucket is BucketOwnerEnforced, so an ACL on the object
    would fail the upload outright.
    """

    file_overwrite = False

    @property
    def location(self):
        return settings.PUBLIC_MEDIA_LOCATION

    @property
    def custom_domain(self):
        # Set, so url() returns a plain unsigned URL that caches well.
        return settings.AWS_S3_CUSTOM_DOMAIN


class PrivateMediaStorage(S3Boto3Storage):
    """Respondent submissions: photos, audio, whatever an answer carries.

    Stored outside every publicly readable prefix and served only through a
    signed URL that expires. A URL is not an access control: links leak into
    logs, Referer headers, exported archives and screenshots, and a photograph
    of someone's street or a recording of their voice is not a survey cover.

    Nothing writes here yet — the respondent upload question type is a separate
    change. The tier exists first so that change cannot land files in the
    public prefix by accident.
    """

    file_overwrite = False
    querystring_auth = True

    @property
    def location(self):
        return settings.PRIVATE_MEDIA_LOCATION

    @property
    def custom_domain(self):
        # Must be None: S3Boto3Storage.url() skips signing entirely when a
        # custom domain is set, which would hand out permanent public links to
        # objects the bucket policy deliberately keeps private.
        return None
