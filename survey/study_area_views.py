"""The study area in the editor and on the respondent page (change map-layers-study-area, spec
survey-study-area). Every write goes through `survey.services.study_area`; the place lookup through
`survey.study_area_lookup`. The respondent page reads the outline from `survey_study_area_geojson`,
gated like a reference layer, never inlined.
"""
import json

from django.conf import settings
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET, require_POST

from .layers import layer_owner, layers_for
from .permissions import (SURVEY_ROLE_RANK, get_effective_survey_role, org_permission_required,
                          survey_permission_required)
from .services import study_area as svc_area
from .services.context import Actor
from .services.errors import ValidationFailed

LOOKUP_RATE = '30/m'


def _enabled_or_404():
    if not settings.MAP_REFERENCE_LAYERS:
        raise Http404


def _area_payload(survey, section=None):
    if section is not None:
        return {'area': svc_area.describe(svc_area.section_row(section)), 'mode': svc_area.section_mode(section)}
    return {'area': svc_area.describe(svc_area.get(survey))}


def _section_param(request, survey):
    """The map section a request names (`section`, GET or POST) for its own area (change
    section-study-area), or None for the survey's area. 404 for a section of another survey."""
    from .models import SurveySection
    raw = request.POST.get('section') if request.method == 'POST' else None
    raw = raw or request.GET.get('section')
    if not raw:
        return None
    return get_object_or_404(SurveySection, pk=raw if str(raw).isdigit() else 0, survey_header=survey)


def _back_url(survey, section):
    url = reverse('editor_survey_detail', args=[survey.uuid])
    return f'{url}?section={section.pk}' if section is not None else f'{url}?panel=settings'


def _bool(value):
    return str(value).lower() in ('1', 'true', 'on', 'yes')


@survey_permission_required('editor')
@require_GET
def editor_study_area(request, survey_uuid):
    """The study area editor: place search, candidates, vertex editing, other sources, rules. With
    `?section=<id>` it edits that map section's own area (change section-study-area), starting from
    the survey's outline (unsaved) when the section has none yet."""
    _enabled_or_404()
    survey = request.survey
    section = _section_param(request, survey)
    if section is not None and not section.has_map:
        raise Http404
    from .layers import has_polygons
    polygon_layers = [layer for layer in layers_for(survey).filter(source='upload').order_by('position', 'id')
                      if has_polygons(layer)]
    survey_area = svc_area.get(survey)
    if section is None:
        area = survey_area
        start_area = None
    else:
        row = svc_area.section_row(section)
        area = row if row is not None and row.geometry is not None else None
        start_area = survey_area if area is None else None
    primary = (survey.available_languages or ['en'])[0]
    return render(request, 'editor/study_area.html', {
        'survey': survey,
        'section': section,
        'area': area,
        'area_json': json.dumps(svc_area.describe(area)) if area else 'null',
        'start_area_json': json.dumps(svc_area.describe(start_area)) if start_area else 'null',
        'message': (area.message or {}).get(primary, '') if area else '',
        'polygon_layers': polygon_layers,
        'widths': (50, 100, 200),
        'start': _start_position(survey),
        'back_url': _back_url(survey, section),
    })


def _start_position(survey):
    """Where the editor's map opens before there is an area: the survey's own map start, else the
    first section that has one, else the world."""
    from .models import SurveySection
    point, zoom = survey.start_map_postion, survey.start_map_zoom
    if point is None:
        section = (SurveySection.objects.filter(survey_header=survey, start_map_postion__isnull=False)
                   .order_by('id').first())
        if section is not None:
            point, zoom = section.start_map_postion, section.start_map_zoom
    if point is None:
        return {'lat': 20, 'lng': 0, 'zoom': 2}
    return {'lat': point.y, 'lng': point.x, 'zoom': zoom or 13}


def _limited(request):
    from django_ratelimit import ALL
    from django_ratelimit.core import is_ratelimited
    try:
        return is_ratelimited(request=request, group='study_area_lookup', fn=None,
                              key=lambda _g, r: str(r.user.pk), rate=LOOKUP_RATE, method=ALL, increment=True)
    except Exception:  # noqa: BLE001 — a blind limiter fails open
        return False


@survey_permission_required('editor')
@require_GET
def editor_study_area_lookup(request, survey_uuid):
    """Up to five OpenStreetMap candidates for a place name (`q`)."""
    _enabled_or_404()
    from .study_area_lookup import LookupUnavailable, search
    if _limited(request):
        return JsonResponse({'error': _('Too many searches. Wait a minute and try again.')}, status=429)
    try:
        candidates = search(request.GET.get('q', ''), getattr(request, 'LANGUAGE_CODE', 'en') or 'en')
    except LookupUnavailable:
        return JsonResponse({'error': _('Could not reach OpenStreetMap. Upload a boundary or draw it instead.'),
                             'unavailable': True}, status=503)
    return JsonResponse({'candidates': candidates})


@survey_permission_required('editor')
@require_GET
def editor_study_area_candidate(request, survey_uuid):
    """The polygon one candidate becomes (`osm_ref`; `width` for a street corridor), not saved."""
    _enabled_or_404()
    from .study_area_lookup import DEFAULT_WIDTH, candidate_outline
    try:
        width = int(request.GET.get('width') or DEFAULT_WIDTH)
    except ValueError:
        width = DEFAULT_WIDTH
    found = candidate_outline(request.GET.get('osm_ref'), width)
    if found is None or not found['geometry']:
        return JsonResponse({'error': _('Search again: this result is no longer at hand.')}, status=404)
    return JsonResponse(found)


@survey_permission_required('editor')
@require_POST
def editor_study_area_save(request, survey_uuid):
    """Save the confirmed outline (`geometry` GeoJSON) with where it came from — the survey's area,
    or with `section` that section's own area."""
    _enabled_or_404()
    survey = request.survey
    section = _section_param(request, survey)
    try:
        geometry = json.loads(request.POST.get('geometry') or 'null')
    except ValueError:
        return JsonResponse({'error': svc_area.GEOMETRY_MESSAGE}, status=400)
    kwargs = dict(source=request.POST.get('source') or 'draw',
                  place_name=request.POST.get('place_name', ''), osm_ref=request.POST.get('osm_ref', ''))
    try:
        if section is not None:
            svc_area.set_section_area(Actor.from_request(request), section, geometry, **kwargs)
        else:
            svc_area.set_area(Actor.from_request(request), survey, geometry, **kwargs)
    except ValidationFailed as exc:
        return JsonResponse({'error': exc.message}, status=400)
    return JsonResponse(_area_payload(survey, section))


@survey_permission_required('editor')
@require_POST
def editor_study_area_settings(request, survey_uuid):
    """Fog, the refusal rule and the message (primary language; others are in Translations) of the
    survey's area, or with `section` of that section's own area."""
    _enabled_or_404()
    survey = request.survey
    section = _section_param(request, survey)
    area = svc_area.section_row(section) if section is not None else svc_area.get(survey)
    message = None
    if 'message' in request.POST:
        primary = (survey.available_languages or ['en'])[0]
        message = {**(area.message if area else {}), primary: request.POST.get('message', '')}
    kwargs = dict(fog=_bool(request.POST['fog']) if 'fog' in request.POST else None,
                  refuse_outside=(_bool(request.POST['refuse_outside'])
                                  if 'refuse_outside' in request.POST else None),
                  message=message)
    try:
        if section is not None:
            svc_area.update_section_settings(Actor.from_request(request), section, **kwargs)
        else:
            svc_area.update_settings(Actor.from_request(request), survey, **kwargs)
    except ValidationFailed as exc:
        return JsonResponse({'error': exc.message}, status=400)
    return JsonResponse(_area_payload(survey, section))


@survey_permission_required('editor')
@require_POST
def editor_study_area_clear(request, survey_uuid):
    """Remove the survey's area, or with `section` return that section to the survey's area (its
    own outline is kept for a later Own area)."""
    _enabled_or_404()
    section = _section_param(request, request.survey)
    if section is not None:
        try:
            svc_area.set_section_mode(Actor.from_request(request), section, svc_area.KIND_SURVEY)
        except ValidationFailed as exc:
            return JsonResponse({'error': exc.message}, status=400)
    else:
        svc_area.clear(Actor.from_request(request), request.survey)
    return HttpResponse(status=204)


@survey_permission_required('editor')
@require_POST
def editor_study_area_section_mode(request, survey_uuid):
    """The Map card's choice for a section (change section-study-area): `survey`, `own` or `none`.
    Own area without a stored outline answers the editor's URL to draw one; nothing is saved."""
    _enabled_or_404()
    survey = request.survey
    section = _section_param(request, survey)
    if section is None:
        return JsonResponse({'error': _('Pick a section.')}, status=400)
    mode = request.POST.get('mode', '')
    if mode == svc_area.KIND_OWN:
        row = svc_area.section_row(section)
        if row is None or row.geometry is None:
            return JsonResponse({'editor_url': reverse('editor_study_area', args=[survey.uuid])
                                 + f'?section={section.pk}'})
    try:
        svc_area.set_section_mode(Actor.from_request(request), section, mode)
    except ValidationFailed as exc:
        return JsonResponse({'error': exc.message}, status=400)
    return JsonResponse(svc_area.describe_section(section))


def _union_of_polygons(features):
    """One MultiPolygon GeoJSON from the polygon features of a file or a layer, or None."""
    from django.contrib.gis.geos import GEOSGeometry, MultiPolygon
    parts = []
    for feature in features:
        geometry = feature.get('geometry') if isinstance(feature, dict) else None
        if not geometry or geometry.get('type') not in ('Polygon', 'MultiPolygon'):
            continue
        try:
            geom = GEOSGeometry(json.dumps(geometry), srid=4326)
        except Exception:  # noqa: BLE001 — a broken part is skipped
            continue
        parts += list(geom) if geom.geom_type == 'MultiPolygon' else [geom]
    if not parts:
        return None
    return json.loads(MultiPolygon(*parts, srid=4326).unary_union.geojson)


@survey_permission_required('editor')
@require_POST
def editor_study_area_upload(request, survey_uuid):
    """Read a boundary file (same formats and conversion as layers) into the editor; not saved."""
    _enabled_or_404()
    from .layers import MAX_LAYER_BYTES, LayerValidationError, validate_layer_upload
    from .services import layers as svc_layers
    f = request.FILES.get('file')
    if not f:
        return JsonResponse({'error': _('Choose a file.')}, status=400)
    if f.size > MAX_LAYER_BYTES:
        return JsonResponse({'error': _('The file is larger than 10 MB.')}, status=400)
    data, name = f.read(), f.name or 'upload.geojson'
    ext = ('.' + name.rsplit('.', 1)[-1].lower()) if '.' in name else '.geojson'
    try:
        if ext in svc_layers.DATA_READER_EXTS:
            features, _profile = svc_layers._read_with_data_reader(data, name)
        else:
            try:
                features, _p, _z = validate_layer_upload(data)
            except LayerValidationError as exc:
                if 'projected coordinate system' not in str(exc):
                    return JsonResponse({'error': str(exc)}, status=400)
                features, _profile = svc_layers._read_with_data_reader(data, 'upload.geojson')
    except svc_layers.LayerError as exc:
        return JsonResponse({'error': exc.message}, status=400)
    geometry = _union_of_polygons(features)
    if geometry is None:
        return JsonResponse({'error': _('The file has no area in it. A study area is a polygon.')}, status=400)
    return JsonResponse({'geometry': geometry})


@survey_permission_required('editor')
@require_POST
def editor_study_area_from_layer(request, survey_uuid):
    """Make a polygon layer of the survey its study area. From the Add layer dialog the layer then
    leaves the survey's maps (it stays in Data); from the editor's "Use a layer" it stays."""
    _enabled_or_404()
    from .models import LayerObject
    from .services import layers as svc_layers
    survey = request.survey
    layer = get_object_or_404(layers_for(survey), pk=request.POST.get('layer') or 0)
    features = [{'geometry': json.loads(geom.geojson)} for geom in
                LayerObject.objects.filter(layer=layer).values_list('geometry', flat=True)]
    geometry = _union_of_polygons(features)
    if geometry is None:
        return JsonResponse({'error': _('This layer has no area in it. A study area is a polygon.')}, status=400)
    actor = Actor.from_request(request)
    section = _section_param(request, survey)
    try:
        if section is not None:
            svc_area.set_section_area(actor, section, geometry, source='layer', place_name=layer.name)
        else:
            svc_area.set_area(actor, survey, geometry, source='layer', place_name=layer.name)
    except ValidationFailed as exc:
        return JsonResponse({'error': exc.message}, status=400)
    if section is None and _bool(request.POST.get('remove_layer', '1')):
        try:
            svc_layers.delete(actor, layer, survey)
        except svc_layers.LayerError:
            pass   # a question asks about it: it stays a layer too
    return JsonResponse({**_area_payload(survey),
                         'editor_url': reverse('editor_study_area', args=[layer_owner(survey).uuid])})


@require_GET
def survey_study_area_geojson(request, survey_slug):
    """The study area outline for the respondent map, under the survey's own access rules (a
    collaborator reads it in every status, like a reference layer): the survey's, or with
    `?section=<id>` that section's own area. 404 when there is none."""
    _enabled_or_404()
    from .access_control import check_survey_access
    from .views import resolve_survey
    survey = resolve_survey(survey_slug)
    role = get_effective_survey_role(request.user, survey)
    is_collaborator = SURVEY_ROLE_RANK.get(role, -1) >= SURVEY_ROLE_RANK['viewer']
    if not is_collaborator and check_survey_access(request, survey) is not None:
        raise Http404
    area = svc_area.get(survey)
    section_id = request.GET.get('section')
    if section_id:
        # A section's own area (change section-study-area); the section must be one of this survey's.
        from .models import SurveySection
        section = SurveySection.objects.filter(pk=section_id if str(section_id).isdigit() else 0,
                                               survey_header=survey).first()
        if section is None:
            raise Http404
        kind, area = svc_area.effective(section)
        if kind != svc_area.KIND_OWN:
            raise Http404
    if area is None:
        raise Http404
    # A FeatureCollection, so the Responses map draws it with the reference layer factory too.
    body = json.dumps({'type': 'FeatureCollection', 'features': [{
        'type': 'Feature', 'properties': {'fog': area.fog, 'refuse_outside': area.refuse_outside},
        'geometry': json.loads(area.geometry.geojson)}]})
    response = HttpResponse(body, content_type='application/geo+json')
    response['Cache-Control'] = 'private, max-age=60'
    return response


@org_permission_required('editor')
@require_GET
def editor_place_boundary(request):
    """The create page's study area proposal (change map-layers-study-area, D8b): the outline of
    the place `q` names — or of a candidate it already got (`osm_ref`, with `width` for a street) —
    cleaned like a saved study area. Nothing is stored; the form posts what the creator kept."""
    _enabled_or_404()
    from .study_area_lookup import LookupUnavailable
    from .study_area_wizard import boundary_for
    if _limited(request):
        return JsonResponse({'error': _('Too many searches. Wait a minute and try again.')}, status=429)
    try:
        width = int(request.GET.get('width') or 0) or None
    except ValueError:
        width = None
    try:
        found = boundary_for(query=request.GET.get('q', ''), osm_ref=request.GET.get('osm_ref') or None,
                             width=width, language=getattr(request, 'LANGUAGE_CODE', 'en') or 'en')
    except LookupUnavailable:
        return JsonResponse({'found': False, 'unavailable': True})
    if found is None:
        return JsonResponse({'found': False})
    return JsonResponse({'found': True, **found})
