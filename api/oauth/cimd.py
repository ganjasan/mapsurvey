"""Client ID metadata documents (change oauth-server, D8).

The toolkit's `SafeMetadataFetcher` already refuses `http`, resolves the host
and refuses every non-global address (private, loopback, link-local with the
cloud metadata address, CGNAT, NAT64-embedded, reserved), follows no redirect,
stops at 5 s and 16 KB, and the resolver checks `client_id` against the URL,
caches by `Cache-Control` within [5 min, 24 h] and backs off a failing URL.
What it fetched still goes through our rules -- the same ones DCR applies --
before it becomes an `Application`.
"""
from django.core.exceptions import ValidationError
from oauth2_provider.cimd import CIMDError, SafeMetadataFetcher

from . import dcr


class MetadataFetcher(SafeMetadataFetcher):
    def fetch(self, client_id):
        metadata, max_age = super().fetch(client_id)
        try:
            metadata = dcr.normalise_metadata(metadata)
        except ValidationError as exc:
            raise CIMDError('; '.join(exc.messages)) from exc
        return metadata, max_age
