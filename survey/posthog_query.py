"""Read access to PostHog's event table (HogQL) for staff tooling.

The project key can only write; reading needs a personal API key, which lives
in the operator's shell for the one command that needs it and never in
`render.yaml`. Two callers: `check_posthog_funnel_parity` (reconciles the
funnel) and `backfill_creator_returns` (restores return rows from before the
`CreatorSurveyActivity` table existed).
"""
import json
import os
import urllib.error
import urllib.request

from django.conf import settings


class PostHogQueryError(Exception):
    pass


def credentials(personal_api_key=None):
    """(host, project_id, key) or raise PostHogQueryError naming what is missing."""
    key = personal_api_key or os.environ.get('POSTHOG_PERSONAL_API_KEY')
    if not key:
        raise PostHogQueryError(
            'A personal API key is required to query PostHog. Pass --personal-api-key '
            'or set POSTHOG_PERSONAL_API_KEY. (The project key can only write.)'
        )
    project_id = getattr(settings, 'POSTHOG_PROJECT_ID', '') or os.environ.get('POSTHOG_PROJECT_ID')
    if not project_id:
        raise PostHogQueryError('Set POSTHOG_PROJECT_ID to the numeric project id.')
    return settings.POSTHOG_API_HOST, project_id, key


def query_url(host, project_id):
    return f'{host.replace("://eu.i.", "://eu.").replace("://us.i.", "://us.")}/api/projects/{project_id}/query/'


def hogql(sql, host, project_id, key, timeout=60):
    """Run one HogQL query; returns the list of result rows."""
    body = json.dumps({'query': {'kind': 'HogQLQuery', 'query': sql}}).encode()
    req = urllib.request.Request(
        query_url(host, project_id), data=body,
        headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.load(resp)
    except urllib.error.HTTPError as exc:
        raise PostHogQueryError(f'PostHog query failed: {exc.code} {exc.read()[:400]!r}') from exc
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise PostHogQueryError(f'PostHog query failed: {exc}') from exc
    return payload.get('results', [])
