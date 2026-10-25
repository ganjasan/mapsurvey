"""Client ID metadata documents (change oauth-server, D8).

The toolkit's `SafeMetadataFetcher` already refuses `http`, resolves the host
and refuses every non-global address (private, loopback, link-local with the
cloud metadata address, CGNAT, NAT64-embedded, reserved), follows no redirect,
stops at 5 s and 16 KB, and the resolver checks `client_id` against the URL,
caches by `Cache-Control` within [5 min, 24 h] and backs off a failing URL.
What it fetched still goes through our rules -- the same ones DCR applies --
before it becomes an `Application`.

The toolkit takes only public CIMD clients (`token_endpoint_auth_method`
"none"). ChatGPT's document declares `private_key_jwt` as its method but lists
"none" among `token_endpoint_auth_methods_supported`, and our server metadata
offers no `private_key_jwt`, so ChatGPT authenticates as a public client with
PKCE anyway. When a document says it can do "none", we register it as such
(change fix-chatgpt-cimd-auth-method); one that cannot is still refused.
"""
from django.core.exceptions import ValidationError
from oauth2_provider.cimd import CIMDError, SafeMetadataFetcher

from . import dcr

PUBLIC_AUTH_METHOD = 'none'
# What a client that authenticates with a key pair adds; meaningless once it is public.
KEY_AUTH_MEMBERS = ('token_endpoint_auth_methods_supported', 'token_endpoint_auth_signing_alg')


def prefer_public_auth(metadata):
    """Register as a public client when the document says it can be one."""
    method = metadata.get('token_endpoint_auth_method', PUBLIC_AUTH_METHOD)
    supported = metadata.get('token_endpoint_auth_methods_supported')
    if method == PUBLIC_AUTH_METHOD or not isinstance(supported, list) or PUBLIC_AUTH_METHOD not in supported:
        return metadata
    out = {k: v for k, v in metadata.items() if k not in KEY_AUTH_MEMBERS}
    out['token_endpoint_auth_method'] = PUBLIC_AUTH_METHOD
    return out


class MetadataFetcher(SafeMetadataFetcher):
    def fetch(self, client_id):
        metadata, max_age = super().fetch(client_id)
        try:
            metadata = dcr.normalise_metadata(prefer_public_auth(metadata))
        except ValidationError as exc:
            raise CIMDError('; '.join(exc.messages)) from exc
        return metadata, max_age
