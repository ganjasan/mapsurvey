"""The workspace's map style library (change map-styles-library, #542; epic #545).

`/org/<slug>/map-styles/` lists the five presets and the workspace's own styles; every
member may look. Duplicate, rename and delete are POSTs for owner/admin/editor. Creating
a style (today: duplicating one) is the `map_styles` Pro feature and counts a trial use;
using a style that exists is never gated (billing/features.py). A duplicate is the same
settings under a new name, published to Mapbox by `survey.map_styles.tasks` — the page
polls while a version is pending, like the import-jobs card.
"""
import math
from urllib.parse import urlencode

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from billing import trial as billing_trial
from billing.gates import feature_required

from . import basemaps, map_start, product_events
from .map_styles.tasks import delete_mapbox_style, publish_map_style_version
from .models import MapStyle, MapStyleVersion, Organization
from .permissions import get_org_membership

ACTING_ROLES = ('owner', 'admin', 'editor')
PREVIEW_ZOOM = 12
# Copenhagen, the demo survey's city: a workspace with no positioned survey previews here.
PREVIEW_FALLBACK = (55.6795, 12.5780)
NAME_MAX = 120


def _member(request, slug):
    org = get_object_or_404(Organization, slug=slug)
    membership = get_org_membership(request.user, org)
    return org, membership


def _tile_xy(lat, lng, zoom):
    n = 2 ** zoom
    x = int((lng + 180) / 360 * n)
    lat_r = math.radians(lat)
    y = int((1 - math.log(math.tan(lat_r) + 1 / math.cos(lat_r)) / math.pi) / 2 * n)
    return x, y


def preview_url(basemap, org):
    """One tile over the workspace's start position: a picture of the style that costs one
    tile request and is cached by the browser."""
    found = map_start._org_survey_position(org)
    lat, lng = (found.lat, found.lng) if found else PREVIEW_FALLBACK
    zoom = PREVIEW_ZOOM if basemap.tile_size == 256 else PREVIEW_ZOOM - 1
    x, y = _tile_xy(lat, lng, zoom)
    return (basemap.tile_url.replace('{z}', str(zoom)).replace('{x}', str(x)).replace('{y}', str(y))
            .replace('{accessToken}', settings.MAPBOX_ACCESS_TOKEN))


def _cards(org):
    usage = basemaps.usage(org)
    styles = basemaps._styles_for(org)
    cards = []
    for style in styles:
        version = basemaps._version_for(style, None)
        latest = style.latest()
        basemap = basemaps._from_version(style, version) if version else None
        cards.append({
            'style': style,
            'basemap': basemap,
            'preview': preview_url(basemap, org) if basemap else '',
            'usage': usage.get(str(style.uuid), 0) if not style.is_preset else None,
            'pending': latest is not None and latest.status == MapStyleVersion.PENDING,
            'failed': latest is not None and latest.status == MapStyleVersion.FAILED,
            'error': latest.error if latest is not None else '',
            'latest': latest,
        })
    return cards


@login_required
def org_map_styles(request, slug):
    org, membership = _member(request, slug)
    if membership is None:
        return HttpResponseForbidden()
    cards = _cards(org)
    context = {
        'org': org,
        'cards': cards,
        'can_act': membership.role in ACTING_ROLES,
        'polling': any(c['pending'] for c in cards),
    }
    template = 'org/_map_style_cards.html' if request.headers.get('HX-Request') else 'org/map_styles.html'
    return render(request, template, context)


def _acting(request, slug):
    org, membership = _member(request, slug)
    if membership is None or membership.role not in ACTING_ROLES:
        return org, None
    return org, membership


@login_required
@require_POST
def org_map_style_duplicate(request, slug, uuid):
    org, membership = _acting(request, slug)
    if membership is None:
        return HttpResponseForbidden()
    source = get_object_or_404(MapStyle, uuid=uuid, archived_at__isnull=True)
    if not source.is_preset and source.organization_id != org.pk:
        return HttpResponseForbidden()
    if not source.can_duplicate:
        messages.error(request, _('This base map cannot be duplicated.'))
        return redirect('org_map_styles', slug=org.slug)
    version = source.latest_ready()
    if version is None:
        messages.error(request, _('This style has no published version to copy yet.'))
        return redirect('org_map_styles', slug=org.slug)
    # One style created is one use of `map_styles`; the first one of a workspace that never
    # had a trial starts it (change pro-trial-auto).
    if not billing_trial.use(org, 'map_styles', actor=request.user):
        return feature_required(request, org, 'map_styles')
    billing_trial.flash_started(request, org)
    name = (request.POST.get('name') or _('%(name)s copy') % {'name': source.name}).strip()[:NAME_MAX]
    with transaction.atomic():
        style = MapStyle.objects.create(organization=org, name=name or source.name, base=source.base,
                                        created_by=request.user)
        new_version = MapStyleVersion.objects.create(
            style=style, number=1, settings=dict(version.settings), provider=MapStyleVersion.MAPBOX,
            attribution=version.attribution, max_zoom=version.max_zoom, created_by=request.user)
        transaction.on_commit(lambda: publish_map_style_version.delay(new_version.pk))
    product_events.emit('map_style_created', request.user.pk, {
        'organization_id': org.pk, 'style_id': style.pk, 'source': source.key or 'workspace'})
    messages.success(request, _('“%(name)s” is being published. It appears in survey settings once it is ready.')
                     % {'name': style.name})
    return redirect('org_map_styles', slug=org.slug)


@login_required
@require_POST
def org_map_style_rename(request, slug, uuid):
    org, membership = _acting(request, slug)
    if membership is None:
        return HttpResponseForbidden()
    style = get_object_or_404(MapStyle, uuid=uuid, organization=org, archived_at__isnull=True)
    name = (request.POST.get('name') or '').strip()[:NAME_MAX]
    if not name:
        messages.error(request, _('A style needs a name.'))
    else:
        style.name = name
        style.save(update_fields=['name', 'updated_at'])
    return redirect('org_map_styles', slug=org.slug)


@login_required
@require_POST
def org_map_style_delete(request, slug, uuid):
    org, membership = _acting(request, slug)
    if membership is None:
        return HttpResponseForbidden()
    style = get_object_or_404(MapStyle, uuid=uuid, organization=org, archived_at__isnull=True)
    using = basemaps.surveys_using(style)
    if using:
        messages.error(request, _('“%(name)s” is used by %(surveys)s. Choose another base map there first.')
                       % {'name': style.name, 'surveys': ', '.join(f'“{n}”' for n in using)})
        return redirect('org_map_styles', slug=org.slug)
    hosted = list(style.versions.filter(status=MapStyleVersion.READY)
                  .exclude(mapbox_style_id='').values_list('mapbox_style_id', flat=True))
    style.archived_at = timezone.now()
    style.save(update_fields=['archived_at', 'updated_at'])
    for style_id in hosted:
        transaction.on_commit(lambda sid=style_id: delete_mapbox_style.delay(sid))
    product_events.emit('map_style_deleted', request.user.pk, {'organization_id': org.pk, 'style_id': style.pk})
    messages.success(request, _('“%(name)s” was deleted.') % {'name': style.name})
    return redirect('org_map_styles', slug=org.slug)


@login_required
@require_POST
def org_map_style_retry(request, slug, uuid):
    """Re-enqueue a failed version (the Styles API was down, the token was missing)."""
    org, membership = _acting(request, slug)
    if membership is None:
        return HttpResponseForbidden()
    style = get_object_or_404(MapStyle, uuid=uuid, organization=org, archived_at__isnull=True)
    latest = style.latest()
    if latest is not None and latest.status == MapStyleVersion.FAILED:
        MapStyleVersion.objects.filter(pk=latest.pk).update(status=MapStyleVersion.PENDING, error='')
        transaction.on_commit(lambda: publish_map_style_version.delay(latest.pk))
    return redirect('org_map_styles', slug=org.slug)
