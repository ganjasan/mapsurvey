"""`personal-access-tokens`: minting, storage, format, audit (change auth-core)."""
import re
from datetime import timedelta

from django.db import connection
from django.test import TestCase
from django.utils import timezone
from oauth2_provider.models import AccessToken

from survey.models import AuditLog

from .. import scopes, tokens
from ..models import AUDIENCE_API, KIND_PERSONAL, TokenProfile
from .helpers import make_free_org, make_member, make_org, mint


class MintingTest(TestCase):
    def setUp(self):
        self.org, self.owner = make_org()

    def test_value_format(self):
        """
        GIVEN a minted token
        WHEN its value is inspected
        THEN it is msk_ plus at least 40 URL-safe characters
        """
        value, profile = mint(self.owner)
        self.assertRegex(value, r'^msk_[A-Za-z0-9_-]{40,}$')
        self.assertEqual(profile.suffix, value[-4:])
        self.assertEqual(tokens.display(profile), 'msk_…' + value[-4:])

    def test_only_a_hash_is_stored(self):
        """
        GIVEN a minted value
        WHEN every column of the token row is read
        THEN the value appears nowhere and the checksum is sha256 of it
        """
        value, profile = mint(self.owner)
        row = AccessToken.objects.get(pk=profile.token_id)
        self.assertEqual(row.token, '')
        self.assertEqual(row.token_checksum, tokens.checksum(value))
        with connection.cursor() as cur:
            cur.execute('SELECT * FROM oauth2_provider_accesstoken WHERE id = %s', [row.pk])
            self.assertNotIn(value, str(cur.fetchall()))
            cur.execute('SELECT * FROM api_tokenprofile WHERE token_id = %s', [row.pk])
            self.assertNotIn(value, str(cur.fetchall()))

    def test_row_shape(self):
        """
        GIVEN a mint with scopes, audiences and no binding
        WHEN the rows are read
        THEN the access token has no application, the registry's scope string, and the profile is personal
        """
        value, profile = mint(self.owner, scopes_=(scopes.SURVEYS_WRITE, scopes.SURVEYS_READ), audiences=(AUDIENCE_API,))
        self.assertIsNone(profile.token.application_id)
        self.assertEqual(profile.token.scope, 'surveys:read surveys:write')
        self.assertEqual(profile.kind, KIND_PERSONAL)
        self.assertEqual(profile.audiences, ['api'])
        self.assertIsNone(profile.organization)
        self.assertIsNone(profile.last_used_at)

    def test_values_are_unique(self):
        """
        GIVEN two mints
        WHEN their values are compared
        THEN they differ and both resolve to their own row
        """
        v1, p1 = mint(self.owner)
        v2, p2 = mint(self.owner)
        self.assertNotEqual(v1, v2)
        self.assertNotEqual(p1.token_id, p2.token_id)

    def test_organization_must_be_a_membership(self):
        """
        GIVEN a workspace the user is not a member of
        WHEN a token bound to it is minted
        THEN ValueError and no row
        """
        other, _ = make_free_org('Other', 'other_owner')
        with self.assertRaises(ValueError):
            mint(self.owner, organization=other)
        self.assertEqual(TokenProfile.objects.count(), 0)
        self.assertEqual(AccessToken.objects.count(), 0)

    def test_unknown_scope_refused(self):
        """
        GIVEN a scope not in the registry
        WHEN minting
        THEN ValueError and no row
        """
        with self.assertRaises(ValueError):
            mint(self.owner, scopes_=('admin:all',))
        self.assertEqual(AccessToken.objects.count(), 0)

    def test_expiry_choices(self):
        """
        GIVEN the three expiry choices
        WHEN resolved
        THEN 90 days, 365 days and a century from now
        """
        now = timezone.now()
        self.assertEqual(tokens.expires_for(tokens.EXPIRY_90_DAYS, now), now + timedelta(days=90))
        self.assertEqual(tokens.expires_for(tokens.EXPIRY_1_YEAR, now), now + timedelta(days=365))
        self.assertGreater(tokens.expires_for(tokens.EXPIRY_NEVER, now), now + timedelta(days=365 * 99))
        with self.assertRaises(ValueError):
            tokens.expires_for('tomorrow')

    def test_looks_like_token(self):
        """
        GIVEN values of various shapes
        WHEN looks_like_token is asked
        THEN only a well-formed msk_ value passes
        """
        value, _ = mint(self.owner)
        self.assertTrue(tokens.looks_like_token(value))
        for bad in ('', 'msk_', 'abc', 'msk_' + 'x' * 10, 'msk_' + 'x' * 300, 'msk_' + '!' * 45, None):
            self.assertFalse(tokens.looks_like_token(bad), bad)


class RevokeAndPurgeTest(TestCase):
    def setUp(self):
        self.org, self.owner = make_org()

    def test_revoke_keeps_the_row(self):
        """
        GIVEN a token
        WHEN revoked
        THEN revoked_at is set and the row stays for the audit trail
        """
        _, profile = mint(self.owner)
        tokens.revoke(profile)
        profile.refresh_from_db()
        self.assertIsNotNone(profile.revoked_at)
        self.assertTrue(AccessToken.objects.filter(pk=profile.token_id).exists())

    def test_purge_after_retention(self):
        """
        GIVEN tokens revoked or expired 31 days ago, and live ones
        WHEN purge_ended runs
        THEN only the ended-long-ago ones are deleted
        """
        now = timezone.now()
        _, old_revoked = mint(self.owner)
        tokens.revoke(old_revoked, now=now - timedelta(days=31))
        _, fresh_revoked = mint(self.owner)
        tokens.revoke(fresh_revoked, now=now - timedelta(days=2))
        _, old_expired = mint(self.owner, expires=now - timedelta(days=40))
        _, live = mint(self.owner)

        deleted = tokens.purge_ended(now=now)

        self.assertEqual(deleted, 2)
        ids = set(AccessToken.objects.values_list('pk', flat=True))
        self.assertEqual(ids, {fresh_revoked.token_id, live.token_id})

    def test_management_command(self):
        """
        GIVEN an expired-long-ago token
        WHEN purge_api_tokens runs
        THEN it reports one deletion
        """
        from io import StringIO

        from django.core.management import call_command
        mint(self.owner, expires=timezone.now() - timedelta(days=60))
        out = StringIO()
        call_command('purge_api_tokens', stdout=out)
        self.assertIn('deleted 1', out.getvalue())
        self.assertEqual(AccessToken.objects.count(), 0)
