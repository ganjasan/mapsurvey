"""Builders shared by the api test modules (one module per capability, as in billing/)."""
from django.contrib.auth.models import User
from django.test import override_settings

from billing.tests.helpers import make_org, make_sub  # noqa: F401 -- re-exported
from survey.models import Membership, Organization, Question, SurveyHeader, SurveySection

from .. import scopes, tokens
from ..models import AUDIENCE_API, AUDIENCE_MCP

ALL_SCOPES = tuple(scopes.SCOPES)

# Deterministic counters, no Redis dependency: Django swaps the cache on override.
LOCMEM = override_settings(CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
                                                'LOCATION': 'api-tests'}})


def make_user(username='api_user', **kw):
    kw.setdefault('email', f'{username}@example.test')
    return User.objects.create_user(username=username, password='pass', **kw)


def make_member(org, username, role='owner'):
    user = make_user(username)
    Membership.objects.create(user=user, organization=org, role=role)
    return user


def make_pro_org(name='Pro Org', owner_username='pro_owner'):
    org, owner = make_org(name, owner_username)
    make_sub(org)
    return org, owner


def make_free_org(name='Free Org', owner_username='free_owner'):
    return make_org(name, owner_username)


def make_survey(org, name='api_survey'):
    survey = SurveyHeader.objects.create(organization=org, name=name)
    section = SurveySection.objects.create(survey_header=survey, name='sec1')
    question = Question.objects.create(survey_section=section, name='Q1', input_type='text')
    return survey, section, question


def mint(user, scopes_=ALL_SCOPES, audiences=(AUDIENCE_API, AUDIENCE_MCP), organization=None, expires=None,
         label='test token'):
    return tokens.mint_personal_token(user, label, scopes_, audiences, organization=organization, expires=expires)


def bearer(value):
    return {'HTTP_AUTHORIZATION': f'Bearer {value}'}
