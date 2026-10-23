"""Token value generators the toolkit calls through `ACCESS_TOKEN_GENERATOR` /
`REFRESH_TOKEN_GENERATOR` (oauthlib's `token_generator(request)` contract).

A prefix per kind, like GitHub's `ghp_`: `authenticate()` refuses anything
that does not look like one of ours before touching the database, the
scrubber recognises a leaked value, and a refresh token presented as a
bearer is refused on sight. Personal tokens are `msk_` (api.tokens).
"""
import secrets

ACCESS_PREFIX = 'msa_'
REFRESH_PREFIX = 'msr_'
RANDOM_BYTES = 32  # token_urlsafe(32) is 43 characters


def generate_access_token(request=None):
    return ACCESS_PREFIX + secrets.token_urlsafe(RANDOM_BYTES)


def generate_refresh_token(request=None):
    return REFRESH_PREFIX + secrets.token_urlsafe(RANDOM_BYTES)
