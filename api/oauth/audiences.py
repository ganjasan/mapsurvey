"""RFC 8707 `resource` indicators -> the audiences `authenticate()` checks.

`settings.API_RESOURCE_URLS` names each resource server by its identifier
(`{'api': 'https://mapsurvey.org/api/', 'mcp': …}`). A client that sends no
indicator gets both audiences -- a QGIS plug-in has no reason to know the
split -- while ChatGPT, claude.ai and Claude Code send the identifier from
the resource server's metadata and get exactly that one. An indicator that is
a prefix match of no entry is `invalid_target`: issuing a token for a resource
we do not serve would be issuing a token for an attacker's host.

The match is the toolkit's own prefix rule (`validate_resource_as_url_prefix`),
so the resource servers and the issuer agree on what "for this resource" means.
"""
from django.conf import settings
from oauth2_provider.oauth2_validators import validate_resource_as_url_prefix
from oauthlib.oauth2.rfc6749 import errors

from ..models import AUDIENCES


class UnknownResource(ValueError):
    def __init__(self, resource):
        super().__init__(f'unknown resource: {resource}')
        self.resource = resource


def audience_for(resource):
    """The audience key whose identifier is a prefix of `resource`, or None."""
    for key, base in settings.API_RESOURCE_URLS.items():
        if base and validate_resource_as_url_prefix(resource, [base]):
            return key
    return None


def for_resources(resources):
    """Audiences for a list of indicators, in registry order. Raises UnknownResource."""
    if not resources:
        return list(AUDIENCES)
    found = set()
    for resource in resources:
        key = audience_for(resource)
        if key is None:
            raise UnknownResource(resource)
        found.add(key)
    return [a for a in AUDIENCES if a in found]


def invalid_target(resource, request=None, state=None):
    """The oauthlib error the token endpoint and the authorize view raise."""
    return errors.CustomOAuth2Error(
        error='invalid_target',
        description=f"The resource '{resource}' is not served by this authorization server.",
        request=request, state=state,
    )
