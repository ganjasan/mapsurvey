"""What django-oauth-toolkit's access token has no column for.

`TokenProfile` sits beside every `AccessToken` we hand out -- personal tokens
today, OAuth grants from #313 -- so `authenticate()` reads one join whichever
way the token was issued. It never holds the token value: the toolkit stores a
hash (`COMPLIANT_BCP_RFC9700_TOKEN_STORAGE`) and looks tokens up by checksum.
"""
from django.db import models

KIND_PERSONAL = 'personal'
KIND_OAUTH = 'oauth'
KIND_CHOICES = (
    (KIND_PERSONAL, 'Personal token'),
    (KIND_OAUTH, 'OAuth grant'),
)

# Which resource servers a token is good for. A REST token on the MCP host (or
# the reverse) is refused: the two are different products with different
# blast radii, and #313 maps an OAuth `resource` onto exactly one of them.
AUDIENCE_API = 'api'
AUDIENCE_MCP = 'mcp'
AUDIENCES = (AUDIENCE_API, AUDIENCE_MCP)


class TokenProfile(models.Model):
    token = models.OneToOneField('oauth2_provider.AccessToken', on_delete=models.CASCADE, related_name='profile')
    kind = models.CharField(max_length=10, choices=KIND_CHOICES, default=KIND_PERSONAL)
    label = models.CharField(max_length=80, blank=True)
    # The last four characters of the value, so the page can show `msk_…abcd`
    # after the one-time banner is gone. Four characters of a 43-character
    # random suffix identify nothing.
    suffix = models.CharField(max_length=4, blank=True)
    audiences = models.JSONField(default=list)
    # Optional binding: a token that reaches one workspace only. NULL = every
    # workspace the user is a member of.
    organization = models.ForeignKey(
        'survey.Organization', null=True, blank=True, on_delete=models.CASCADE, related_name='api_tokens',
    )
    # Hidden from the page right away, kept 30 days for the audit trail, then
    # purged by `purge_api_tokens`. The toolkit's own revoke() deletes the row,
    # which is why it is not used.
    revoked_at = models.DateTimeField(null=True, blank=True)
    # Touched at most once a minute by authenticate() -- not per request.
    last_used_at = models.DateTimeField(null=True, blank=True)
    created_by_ip = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    # OAuth tokens only: sha256 of the authorization code the family came
    # from (change oauth-server, D4). The toolkit deletes a code on use, so
    # this is how a second redemption still finds -- and revokes -- the tokens
    # the first one produced. Copied along the family on every refresh.
    code_checksum = models.CharField(max_length=64, null=True, blank=True, db_index=True)

    class Meta:
        indexes = [models.Index(fields=['revoked_at', 'kind'])]

    def __str__(self):
        return f'{self.kind} token #{self.token_id} ({self.label})'

    @property
    def is_revoked(self):
        return self.revoked_at is not None
