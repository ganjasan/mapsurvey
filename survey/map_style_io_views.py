"""Export and import of map styles (change map-styles-import-export, #544; epic #545).

Export downloads the portable document of `survey/map_styles/io.py`; import reads one,
normalises it through the editor's controls and creates a workspace style published in
the background, exactly as Duplicate does. Both are the `map_styles` Pro feature: import
counts as creating a style, export needs the feature in force.
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import Http404, HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect
from django.utils.text import slugify
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET, require_POST

from billing import trial as billing_trial
from billing.gates import feature_required

from . import product_events
from .map_style_views import _acting
from .map_styles import io as style_io
from .map_styles.tasks import publish_map_style_version
from .models import MapStyle, MapStyleVersion


@login_required
@require_GET
def org_map_style_export(request, slug, uuid):
    org, membership = _acting(request, slug)
    if membership is None:
        return HttpResponseForbidden()
    if not billing_trial.may(org, 'map_styles'):
        return feature_required(request, org, 'map_styles')
    style = get_object_or_404(MapStyle, uuid=uuid, archived_at__isnull=True)
    if (not style.is_preset and style.organization_id != org.pk) or not style.can_duplicate:
        raise Http404
    body = style_io.export_bytes(style)
    response = HttpResponse(body, content_type='application/json; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="mapsurvey-style-{slugify(style.name) or "style"}.json"'
    product_events.emit('map_style_exported', request.user.pk,
                        {'organization_id': org.pk, 'style_id': style.pk, 'preset': style.key or ''})
    return response


@login_required
@require_POST
def org_map_style_import(request, slug):
    org, membership = _acting(request, slug)
    if membership is None:
        return HttpResponseForbidden()
    upload = request.FILES.get('file')
    data = upload.read(style_io.MAX_BYTES + 1) if upload else b''
    name, base, settings, errors = style_io.parse_document(data)
    if errors:
        for error in errors:
            messages.error(request, _('Could not import the map style: %(reason)s') % {'reason': error})
        return redirect('org_map_styles', slug=org.slug)
    # One style created is one use of `map_styles`, like a duplicate (change pro-trial-auto).
    if not billing_trial.use(org, 'map_styles', actor=request.user):
        return feature_required(request, org, 'map_styles')
    billing_trial.flash_started(request, org)
    with transaction.atomic():
        style = MapStyle.objects.create(organization=org, name=style_io.unique_name(org, name), base=base,
                                        created_by=request.user)
        version = MapStyleVersion.objects.create(style=style, number=1, settings=settings,
                                                 provider=MapStyleVersion.MAPBOX, created_by=request.user)
        transaction.on_commit(lambda: publish_map_style_version.delay(version.pk))
    product_events.emit('map_style_imported', request.user.pk, {'organization_id': org.pk, 'style_id': style.pk})
    messages.success(request, _('“%(name)s” was imported and is being published.') % {'name': style.name})
    return redirect('org_map_styles', slug=org.slug)
