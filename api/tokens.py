"""Minting and revoking personal tokens -- the one write path to the token table.

Spike against django-oauth-toolkit 3.4.1 (2026-10-21): with
`COMPLIANT_BCP_RFC9700_TOKEN_STORAGE=True`, `set_token_value(token, raw)` stashes
the raw value on `_raw_token`, leaves the `token` column blank and lets
`TokenChecksumField.pre_save` write `sha256(raw)` into `token_checksum`; the
validator and our `authenticate()` look tokens up by that checksum. `expires`
is NOT nullable, so "never" is a century ahead. `AccessToken.revoke()` deletes
the row; we keep rows 30 days after revocation instead (profile.revoked_at).
"""
import hashlib
import secrets
from datetime import timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from oauth2_provider.models import AccessToken, set_token_value

from . import scopes as scope_registry
from .models import AUDIENCES, KIND_PERSONAL, TokenProfile

PREFIX = 'msk_'
# Bearer values authenticate() will look up: personal tokens and the
# authorization server's access tokens (api.oauth.tokens). Refresh tokens
# (`msr_`) are deliberately absent -- presented as a bearer they fail here.
BEARER_PREFIXES = (PREFIX, 'msa_')
# token_urlsafe(32) is 43 characters; the regex in the spec asks for 40+.
RANDOM_BYTES = 32
MIN_LENGTH = len(PREFIX) + 40
MAX_LENGTH = 256  # anything longer is not a token of ours; refused before hashing

EXPIRY_90_DAYS = '90d'
EXPIRY_1_YEAR = '1y'
EXPIRY_NEVER = 'never'
EXPIRY_CHOICES = (EXPIRY_90_DAYS, EXPIRY_1_YEAR, EXPIRY_NEVER)

RETENTION_AFTER_END = timedelta(days=30)


def generate_value():
    return PREFIX + secrets.token_urlsafe(RANDOM_BYTES)


def checksum(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def looks_like_token(value):
    return (
        isinstance(value, str)
        and value.startswith(BEARER_PREFIXES)
        and MIN_LENGTH <= len(value) <= MAX_LENGTH
        and all(c.isalnum() or c in '-_' for c in value[len(PREFIX):])
    )


def expires_for(choice, now=None):
    now = now or timezone.now()
    if choice == EXPIRY_90_DAYS:
        return now + timedelta(days=90)
    if choice == EXPIRY_1_YEAR:
        return now + timedelta(days=365)
    if choice == EXPIRY_NEVER:
        return now + timedelta(days=365 * 100)
    raise ValueError(f'unknown expiry choice: {choice!r}')


def display(profile):
    """`msk_…abcd` -- what the page shows after the one-time banner. The value is
    gone, so the suffix was kept on the profile at minting time."""
    return f'{PREFIX}…{profile.suffix}'


@transaction.atomic
def mint_personal_token(user, label, scopes, audiences, organization=None, expires=None, created_by_ip=None):
    """Create a personal token. Returns (value, profile); the value exists
    nowhere else after this call returns."""
    scope_set = scope_registry.normalize(scopes)
    if not scope_set:
        raise ValueError('a token needs at least one scope')
    audience_list = [a for a in AUDIENCES if a in set(audiences)]
    if not audience_list:
        raise ValueError('a token needs at least one audience')
    if organization is not None and not user.memberships.filter(organization=organization).exists():
        raise ValueError('organization binding must be one of the user\'s memberships')
    if expires is None:
        expires = expires_for(EXPIRY_NEVER)

    value = generate_value()
    token = AccessToken(user=user, application=None, scope=scope_registry.to_string(scope_set), expires=expires)
    set_token_value(token, value)
    token.save()
    profile = TokenProfile.objects.create(
        token=token, kind=KIND_PERSONAL, label=label[:80], suffix=value[-4:], audiences=audience_list,
        organization=organization, created_by_ip=created_by_ip or None,
    )
    return value, profile


def revoke(profile, now=None):
    if profile.revoked_at is None:
        profile.revoked_at = now or timezone.now()
        profile.save(update_fields=['revoked_at'])
    return profile


def purge_ended(now=None):
    """Delete tokens expired or revoked longer than the retention ago. Returns the count."""
    now = now or timezone.now()
    cutoff = now - RETENTION_AFTER_END
    qs = AccessToken.objects.filter(profile__isnull=False).filter(
        Q(expires__lt=cutoff) | Q(profile__revoked_at__lt=cutoff)
    )
    count = qs.count()
    qs.delete()
    return count
