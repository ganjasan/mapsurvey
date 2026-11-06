"""Publishing a map style version to Mapbox, in the worker (change map-styles-library, #542).

Why a task and its own queue: creating a hosted style takes about a second and the Styles
API allows 50 writes a minute for the whole account (ADR 0001, measured 2026-11-06), so a
request must never wait on it and a classroom of creators must never hit 429. Both tasks
go to the `styles` queue (`CELERY_TASK_ROUTES`) at 40 writes a minute; the worker consumes
it with `-Q celery,styles` (run_dev.sh, render.yaml). The secret token is read here and
nowhere the web process renders.

A version is `pending` while the task runs, `ready` with its Mapbox id when it succeeds,
`failed` with the API's answer when every retry is spent — the library page shows the
state and offers *Try again*. A `ready` version is never touched again: deleting a style
enqueues the Mapbox delete for each of its versions, nothing is PATCHed.
"""
import logging

from celery import shared_task
from django.conf import settings
from django.core.cache import cache

from .generator import DEFAULT_BASE, MapboxApiError, MapboxStylesClient, apply_settings

logger = logging.getLogger(__name__)

BASE_CACHE_TTL = 24 * 3600
PUBLISH_RETRIES = 3
PUBLISH_RETRY_DELAY = 30


def client():
    """The Styles API client for the configured account; `ValueError` without a token."""
    return MapboxStylesClient(settings.MAPBOX_STYLES_TOKEN, settings.MAPBOX_ACCOUNT)


def base_style(api, base_id):
    """The base style JSON, fetched once a day: every publish of a workspace style starts
    from the same `streets-v12`."""
    key = f'map_styles:base:{base_id}'
    cached = cache.get(key)
    if cached is None:
        cached = api.get_style(base_id)
        cache.set(key, cached, BASE_CACHE_TTL)
    return cached


def hosted_name(version):
    """A name no human typed, unique per version, so the account can be read back."""
    org = version.style.organization
    return f'mapsurvey/{org.slug if org else "preset"}/{version.style.uuid}/v{version.number}'


@shared_task(bind=True, max_retries=PUBLISH_RETRIES, default_retry_delay=PUBLISH_RETRY_DELAY,
             rate_limit='40/m', queue='styles')
def publish_map_style_version(self, version_id):
    from survey.models import MapStyleVersion

    try:
        version = MapStyleVersion.objects.select_related('style', 'style__organization').get(pk=version_id)
    except MapStyleVersion.DoesNotExist:
        logger.warning('publish_map_style_version %s: row gone before publish', version_id)
        return
    if version.status != MapStyleVersion.PENDING:
        return
    try:
        api = client()
        base = base_style(api, version.settings.get('base', DEFAULT_BASE) or version.style.base or DEFAULT_BASE)
        style = apply_settings(base, dict(version.settings, name=hosted_name(version)))
        created, _ = api.create(style)
    except (MapboxApiError, ValueError, OSError) as error:
        retryable = isinstance(error, MapboxApiError) and (error.status == 429 or error.status >= 500)
        if retryable and self.request.retries < self.max_retries:
            raise self.retry(exc=error)
        MapStyleVersion.objects.filter(pk=version.pk, status=MapStyleVersion.PENDING).update(
            status=MapStyleVersion.FAILED, error=str(error)[:2000])
        logger.warning('publish_map_style_version %s failed: %s', version_id, error)
        return
    MapStyleVersion.objects.filter(pk=version.pk, status=MapStyleVersion.PENDING).update(
        status=MapStyleVersion.READY, mapbox_style_id=f'{settings.MAPBOX_ACCOUNT}/{created["id"]}', error='')


@shared_task(bind=True, max_retries=PUBLISH_RETRIES, default_retry_delay=PUBLISH_RETRY_DELAY,
             rate_limit='40/m', queue='styles')
def delete_mapbox_style(self, mapbox_style_id):
    """Remove a hosted style the library no longer references. `<account>/<id>`; a 404
    means it is already gone."""
    if not mapbox_style_id or '/' not in mapbox_style_id:
        return
    account, style_id = mapbox_style_id.split('/', 1)
    if account != settings.MAPBOX_ACCOUNT:
        logger.warning('delete_mapbox_style: %s is not ours, left alone', mapbox_style_id)
        return
    try:
        client().delete(style_id)
    except MapboxApiError as error:
        if error.status == 404:
            return
        if (error.status == 429 or error.status >= 500) and self.request.retries < self.max_retries:
            raise self.retry(exc=error)
        logger.warning('delete_mapbox_style %s failed: %s', mapbox_style_id, error)
    except ValueError as error:
        logger.warning('delete_mapbox_style %s: %s', mapbox_style_id, error)
