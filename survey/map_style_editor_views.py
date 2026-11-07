"""The style editor (change map-styles-editor, #543; epic #545, ADR 0001).

`/org/<slug>/map-styles/<uuid>/edit/` edits a WORKSPACE style (presets are duplicated
first). The page renders the guided controls from `map_styles.controls.CONTROLS`, the
browser asks `preview.json` for a MapLibre-readable style on every change, and Save
creates the next immutable version, published by the same task a duplicate uses. Live
surveys keep the version they pinned; the print tab shows the latest ready version.
"""
import json

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import Http404, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET, require_POST

from billing import trial as billing_trial
from billing.gates import feature_required

from . import basemaps, product_events
from .map_style_views import ACTING_ROLES, NAME_MAX, PREVIEW_FALLBACK, _member
from .map_styles import controls, preview
from .map_styles.tasks import publish_map_style_version
from .models import MapStyle, MapStyleVersion, SurveyHeader

STATIC_FRAME = (900, 550)


def _editable_style(request, slug, uuid):
    """(org, style) for an acting member, else an HTTP response to return."""
    org, membership = _member(request, slug)
    if membership is None or membership.role not in ACTING_ROLES:
        return None, HttpResponseForbidden()
    style = MapStyle.objects.filter(uuid=uuid, organization=org, archived_at__isnull=True).first()
    if style is None:
        raise Http404
    return (org, style), None


def _survey_frames(org):
    """The workspace's positioned surveys, for the preview's survey picker."""
    rows = (SurveyHeader.objects
            .filter(organization=org, is_canonical=True, deleted_at__isnull=True, start_map_postion__isnull=False)
            .order_by('-id').values_list('uuid', 'name', 'start_map_postion', 'start_map_zoom')[:50])
    frames = [{'uuid': str(u), 'name': n, 'lat': p.y, 'lng': p.x, 'zoom': z or 12} for u, n, p, z in rows]
    if not frames:
        frames.append({'uuid': '', 'name': _('Copenhagen (example)'), 'lat': PREVIEW_FALLBACK[0],
                       'lng': PREVIEW_FALLBACK[1], 'zoom': 12})
    return frames


def _version_state(style):
    latest = style.latest()
    ready = style.latest_ready()
    return {
        'latest_number': latest.number if latest else 0,
        'latest_status': latest.status if latest else '',
        'latest_error': (latest.error or '')[:300] if latest else '',
        'ready_number': ready.number if ready else 0,
        'ready_style_id': ready.mapbox_style_id if ready else '',
    }


@login_required
def org_map_style_edit(request, slug, uuid):
    found, refusal = _editable_style(request, slug, uuid)
    if refusal is not None:
        return refusal
    org, style = found
    latest = style.latest()
    values = controls.form_values(latest.settings if latest else {})
    usage = basemaps.usage(org).get(str(style.uuid), 0)
    spec = controls.controls_for_template()
    for item in spec['removals']:
        item['value'] = values[item['key']]
    for pal in spec['palettes']:
        pal['value'] = values[pal['key']]
    state = {
        'values': values,
        'controls': spec,
        'i18n': {
            'unavailable': _('Preview unavailable'),
            'noPrint': _('No published version yet'),
            'printPending': _('Version %n is being published; this frame shows the last published one.'),
            'printUnsaved': _('Unsaved changes are not in this frame yet.'),
            'printVersion': _('Version %n, as the printed form renders it.'),
            'publishing': _('Publishing…'),
            'failed': _('Publishing failed'),
            'published': _('Version %n published'),
        },
        'surveys': _survey_frames(org),
        'version': _version_state(style),
        'urls': {
            'preview': reverse('org_map_style_preview', args=[org.slug, style.uuid]),
            'save': reverse('org_map_style_save', args=[org.slug, style.uuid]),
            'status': reverse('org_map_style_status', args=[org.slug, style.uuid]),
            'library': reverse('org_map_styles', args=[org.slug]),
        },
        'token': settings.MAPBOX_ACCESS_TOKEN,
        'account': settings.MAPBOX_ACCOUNT,
        'frame': list(STATIC_FRAME),
        'name': style.name,
    }
    return render(request, 'org/map_style_editor.html', {
        'org': org, 'style': style, 'state': state,
        'controls': state['controls'], 'values': values, 'usage': usage,
        'can_save': billing_trial.may(org, 'map_styles'),
        'pending': bool(latest and latest.status == MapStyleVersion.PENDING),
    })


@login_required
@require_POST
def org_map_style_preview(request, slug, uuid):
    found, refusal = _editable_style(request, slug, uuid)
    if refusal is not None:
        return refusal
    try:
        raw = json.loads(request.body or b'{}')
    except ValueError:
        return JsonResponse({'error': 'invalid json'}, status=400)
    cleaned, errors = controls.clean_settings(raw)
    try:
        style = preview.maplibre_style(cleaned)
    except preview.PreviewUnavailable as error:
        return JsonResponse({'error': 'preview unavailable', 'detail': str(error)[:200]}, status=503)
    return JsonResponse({'style': style, 'errors': errors})


@login_required
@require_POST
def org_map_style_save(request, slug, uuid):
    found, refusal = _editable_style(request, slug, uuid)
    if refusal is not None:
        return refusal
    org, style = found
    # Editing is Pro like creating (vision FE-8); a Save spends no allowance — the
    # trial counts styles, not versions.
    if not billing_trial.may(org, 'map_styles'):
        return feature_required(request, org, 'map_styles')
    try:
        payload = json.loads(request.body or b'{}') if request.content_type == 'application/json' else request.POST
    except ValueError:
        return JsonResponse({'error': 'invalid json'}, status=400)
    raw = payload.get('settings') if isinstance(payload, dict) and isinstance(payload.get('settings'), dict) else payload
    if not isinstance(raw, dict):
        try:
            raw = json.loads(payload.get('settings') or '{}')
        except (TypeError, ValueError):
            raw = {}
    cleaned, errors = controls.clean_settings(raw)
    if errors:
        return JsonResponse({'errors': errors}, status=400)
    latest = style.latest()
    if latest is not None and latest.status == MapStyleVersion.PENDING:
        return JsonResponse({'error': 'pending', 'message': str(_('The previous version is still being published.'))},
                            status=409)
    name = str(payload.get('name') or style.name).strip()[:NAME_MAX] or style.name
    with transaction.atomic():
        if name != style.name:
            style.name = name
            style.save(update_fields=['name', 'updated_at'])
        version = MapStyleVersion.objects.create(
            style=style, number=(latest.number + 1) if latest else 1, settings=cleaned,
            provider=MapStyleVersion.MAPBOX, created_by=request.user,
            attribution=latest.attribution if latest else MapStyleVersion._meta.get_field('attribution').default,
            max_zoom=latest.max_zoom if latest else 22)
        transaction.on_commit(lambda: publish_map_style_version.delay(version.pk))
    product_events.emit('map_style_saved', request.user.pk,
                        {'organization_id': org.pk, 'style_id': style.pk, 'version': version.number})
    messages.success(request, _('Version %(n)s of “%(name)s” is being published.') % {'n': version.number, 'name': style.name})
    return JsonResponse({'ok': True, 'version': _version_state(style),
                         'redirect': reverse('org_map_style_edit', args=[org.slug, style.uuid])})


@login_required
@require_GET
def org_map_style_status(request, slug, uuid):
    found, refusal = _editable_style(request, slug, uuid)
    if refusal is not None:
        return refusal
    _org, style = found
    return JsonResponse(_version_state(style))
