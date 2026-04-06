import json

from django.core.cache import cache
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import Question, Answer, SurveySession, VALIDATION_STATUS_CHOICES
from .permissions import survey_permission_required
from .analytics import SurveyAnalyticsService, PerformanceAnalyticsService, SessionValidationService
from .events import emit_event


def _parse_filter_param(filters_str):
    """Parse '7:1,3;12:2' into {7: [1, 3], 12: [2]}. Returns {} on error."""
    if not filters_str:
        return {}
    result = {}
    try:
        for part in filters_str.split(';'):
            part = part.strip()
            if not part:
                continue
            qid_str, codes_str = part.split(':', 1)
            qid = int(qid_str)
            codes = [int(c) for c in codes_str.split(',') if c.strip()]
            if codes:
                result[qid] = codes
    except (ValueError, AttributeError):
        return {}
    return result


def _resolve_filtered_session_ids(survey, filter_map):
    """Return set of session PKs matching ALL filters (AND across questions, OR within)."""
    if not filter_map:
        return None

    session_sets = None
    for question_id, codes in filter_map.items():
        q_obj = Q()
        for code in codes:
            q_obj |= Q(selected_choices__contains=[code])
        matching = set(
            Answer.objects
            .filter(
                question_id=question_id,
                question__survey_section__survey_header=survey,
                survey_session__is_deleted=False,
            )
            .filter(q_obj)
            .values_list('survey_session_id', flat=True)
        )
        if session_sets is None:
            session_sets = matching
        else:
            session_sets = session_sets & matching

    return session_sets if session_sets is not None else set()


@survey_permission_required('viewer')
def analytics_dashboard(request, survey_uuid):
    """Full analytics dashboard page for a survey."""
    survey = request.survey
    service = SurveyAnalyticsService(survey)

    overview = service.get_overview()
    hourly_sessions = service.get_hourly_sessions()
    session_hours = service.get_session_hours()
    geo_collection = service.get_geo_feature_collection()
    question_stats = service.get_all_question_stats()
    answer_matrix = service.get_answer_matrix()

    text_question_ids = [
        stat['question'].id for stat in question_stats
        if stat['type'] == 'text'
    ]

    # Performance tab data
    perf_service = PerformanceAnalyticsService(survey)
    funnel = perf_service.get_funnel()

    return render(request, 'editor/analytics_dashboard.html', {
        'survey': survey,
        'effective_role': request.effective_survey_role,
        'total_sessions': overview['total_sessions'],
        'completed_count': overview['completed_count'],
        'completion_rate': overview['completion_rate'],
        'flagged_count': overview['flagged_count'],
        'hourly_data_json': json.dumps(hourly_sessions),
        'session_hours_json': json.dumps(session_hours),
        'geo_json': json.dumps(geo_collection),
        'geo_features_count': len(geo_collection['features']),
        'question_stats': question_stats,
        'answer_matrix_json': json.dumps(answer_matrix),
        'text_question_ids_json': json.dumps(text_question_ids),
        # Performance tab
        'event_summary': perf_service.get_event_summary(),
        'funnel': funnel,
        'funnel_json': json.dumps(funnel),
        'referrer_breakdown': perf_service.get_referrer_breakdown(),
        'device_breakdown': perf_service.get_device_breakdown(),
        'completion_by_referrer': perf_service.get_completion_by_referrer(),
        'page_load_stats': perf_service.get_page_load_stats(),
        'time_on_section': perf_service.get_time_on_section(),
        'campaign_breakdown': perf_service.get_campaign_breakdown(),
    })


@survey_permission_required('viewer')
def analytics_text_answers(request, survey_uuid, question_id):
    """HTMX partial: paginated text answers for a single question."""
    survey = request.survey
    question = get_object_or_404(
        Question,
        id=question_id,
        survey_section__survey_header=survey,
    )

    service = SurveyAnalyticsService(survey)
    try:
        page = int(request.GET.get('page', 1))
    except (ValueError, TypeError):
        page = 1
    try:
        page_size = int(request.GET.get('page_size', 20))
    except (ValueError, TypeError):
        page_size = 20

    filters_str = request.GET.get('filters', '')
    filter_map = _parse_filter_param(filters_str)
    session_ids = _resolve_filtered_session_ids(survey, filter_map)

    result = service.get_text_answers(
        question, page=page, page_size=page_size, session_ids=session_ids,
    )

    return render(request, 'editor/partials/analytics_text_answers.html', {
        'survey': survey,
        'question': question,
        **result,
    })


@survey_permission_required('viewer')
def analytics_session_detail(request, survey_uuid, session_id):
    """HTMX partial: all answers for one session, with mini-map geo data."""
    survey = request.survey
    session = get_object_or_404(SurveySession, id=session_id, survey=survey)

    service = SurveyAnalyticsService(survey)
    answer_rows, geo_features = service.format_session_answers(session)

    return render(request, 'editor/partials/analytics_session_detail.html', {
        'survey': survey,
        'session': session,
        'answer_rows': answer_rows,
        'geo_json': json.dumps({'type': 'FeatureCollection', 'features': geo_features}),
        'has_geo': bool(geo_features),
    })


@survey_permission_required('viewer')
def analytics_table(request, survey_uuid):
    """HTMX partial: paginated attribute table of all sessions."""
    survey = request.survey
    show_trash = request.GET.get('trash') == '1'
    service = SurveyAnalyticsService(survey, include_deleted=show_trash)

    # Reuse existing filter parsing (ignored in trash mode)
    filter_map = _parse_filter_param(request.GET.get('filters', ''))
    session_ids = _resolve_filtered_session_ids(survey, filter_map) if not show_trash else None

    try:
        page = int(request.GET.get('page', 1))
    except (ValueError, TypeError):
        page = 1

    sort_col = request.GET.get('sort', 'start_datetime')
    sort_dir = request.GET.get('dir', 'desc')

    try:
        page_size = int(request.GET.get('page_size', 50))
    except (ValueError, TypeError):
        page_size = 50
    page_size = min(max(page_size, 10), 500)

    # Per-column search: search_<col_key>=value
    col_search = {}
    for k, v in request.GET.items():
        if k.startswith('search_') and v.strip():
            col_search[k[7:]] = v.strip()

    issues_filter_raw = request.GET.get('issues', '').strip()
    issues_filter = [f for f in issues_filter_raw.split(',') if f] if issues_filter_raw else None

    # Typed column filters: cf_<col_key>=v:val1|val2 or r:min|max or d:min|max or t:query
    col_filters = {}
    for k, v in request.GET.items():
        if k.startswith('cf_') and v.strip():
            col_key = k[3:]
            val = v.strip()
            if val.startswith('v:'):
                col_filters[col_key] = {'type': 'values', 'values': val[2:].split('|')}
            elif val.startswith('r:'):
                parts = val[2:].split('|')
                filt = {'type': 'range'}
                if len(parts) >= 1 and parts[0]: filt['min'] = parts[0]
                if len(parts) >= 2 and parts[1]: filt['max'] = parts[1]
                col_filters[col_key] = filt
            elif val.startswith('d:'):
                parts = val[2:].split('|')
                filt = {'type': 'date_range'}
                if len(parts) >= 1 and parts[0]: filt['min'] = parts[0]
                if len(parts) >= 2 and parts[1]: filt['max'] = parts[1]
                col_filters[col_key] = filt
            elif val.startswith('t:'):
                col_filters[col_key] = {'type': 'text', 'query': val[2:]}

    result = service.get_table_page(
        page=page, page_size=page_size, session_ids=session_ids,
        sort_col=sort_col, sort_dir=sort_dir, col_search=col_search,
        show_trash=show_trash, issues_filter=issues_filter,
        col_filters=col_filters,
    )

    return render(request, 'editor/partials/analytics_table.html', {
        'survey': survey,
        'show_trash': show_trash,
        'is_editor': request.effective_survey_role in ('editor', 'owner'),
        'page_size_options': [10, 25, 50, 100, 250, 500],
        'issues_filter': ','.join(issues_filter) if issues_filter else '',
        'issues_filter_list': issues_filter or [],
        'anomaly_counts_json': json.dumps(result.pop('anomaly_counts', {})),
        'unique_values_json': json.dumps(result.pop('unique_values', {})),
        'col_filters_json': json.dumps(col_filters),
        'col_filters_params': {k: v for k, v in request.GET.items() if k.startswith('cf_') and v.strip()},
        **result,
    })


@survey_permission_required('editor')
def analytics_validation_settings(request, survey_uuid):
    """GET: return current validation settings. POST: save new settings."""
    survey = request.survey
    if request.method == 'POST':
        try:
            body = json.loads(request.body)
        except (json.JSONDecodeError, AttributeError):
            return HttpResponse(status=400)
        allowed_keys = {'fast_threshold_seconds', 'duplicate_window_hours'}
        settings = {k: v for k, v in body.items() if k in allowed_keys}
        survey.validation_settings = settings
        survey.save(update_fields=['validation_settings'])
        return HttpResponse(status=204)
    return JsonResponse(survey.validation_settings or {
        'fast_threshold_seconds': 30,
        'duplicate_window_hours': 1,
    })


@survey_permission_required('editor')
@require_POST
def analytics_answer_edit(request, survey_uuid, session_id, question_id):
    """Edit or create an answer value for a session+question pair."""
    session = get_object_or_404(SurveySession, id=session_id, survey=request.survey)
    question = get_object_or_404(
        Question, id=question_id,
        survey_section__survey_header=request.survey,
        parent_question_id__isnull=True,
    )
    try:
        body = json.loads(request.body)
        value = body.get('value')
    except (json.JSONDecodeError, AttributeError):
        return HttpResponse(status=400)

    # Get or create the answer
    answer, _ = Answer.objects.get_or_create(
        survey_session=session, question=question, parent_answer_id__isnull=True,
        defaults={},
    )

    # Set value based on question type
    itype = question.input_type
    if itype in ('text', 'text_line', 'datetime'):
        answer.text = str(value) if value is not None else ''
        answer.save(update_fields=['text'])
    elif itype in ('number', 'range'):
        try:
            answer.numeric = float(value) if value not in (None, '') else None
        except (ValueError, TypeError):
            return HttpResponse(status=400)
        answer.save(update_fields=['numeric'])
    elif itype in ('choice', 'rating'):
        try:
            answer.selected_choices = [int(value)] if value not in (None, '') else []
        except (ValueError, TypeError):
            return HttpResponse(status=400)
        answer.save(update_fields=['selected_choices'])
    elif itype == 'multichoice':
        if not isinstance(value, list):
            return HttpResponse(status=400)
        try:
            answer.selected_choices = [int(v) for v in value]
        except (ValueError, TypeError):
            return HttpResponse(status=400)
        answer.save(update_fields=['selected_choices'])
    else:
        return HttpResponse(status=400)

    return HttpResponse(status=204)


@survey_permission_required('editor')
@require_POST
def analytics_session_update_tags(request, survey_uuid, session_id):
    """Update tags and notes on a session."""
    session = get_object_or_404(SurveySession, id=session_id, survey=request.survey)
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, AttributeError):
        return HttpResponse(status=400)
    if 'tags' in body:
        tags = body['tags']
        if not isinstance(tags, list) or not all(isinstance(t, str) for t in tags):
            return HttpResponse(status=400)
        session.tags = [t.strip() for t in tags if t.strip()]
    if 'notes' in body:
        session.notes = str(body['notes'])[:2000]
    session.save(update_fields=['tags', 'notes'])
    return HttpResponse(status=204)


@survey_permission_required('editor')
@require_POST
def analytics_session_set_status(request, survey_uuid, session_id):
    """Set validation_status on a session."""
    session = get_object_or_404(SurveySession, id=session_id, survey=request.survey, is_deleted=False)
    status = request.POST.get('validation_status', '')
    svc = SessionValidationService()
    try:
        svc.set_status(session, status)
    except ValueError:
        return HttpResponse(status=400)
    return HttpResponse(status=204)


@survey_permission_required('editor')
@require_POST
def analytics_session_trash(request, survey_uuid, session_id):
    """Soft-delete a session (move to trash)."""
    session = get_object_or_404(SurveySession, id=session_id, survey=request.survey, is_deleted=False)
    svc = SessionValidationService()
    svc.trash(session)
    return HttpResponse(status=204, headers={'HX-Trigger': 'sessionTrashed'})


@survey_permission_required('editor')
@require_POST
def analytics_session_restore(request, survey_uuid, session_id):
    """Restore a trashed session."""
    session = get_object_or_404(SurveySession, id=session_id, survey=request.survey, is_deleted=True)
    svc = SessionValidationService()
    svc.restore(session)
    return HttpResponse(status=204, headers={'HX-Trigger': 'sessionRestored'})


@survey_permission_required('editor')
@require_POST
def analytics_session_hard_delete(request, survey_uuid, session_id):
    """Permanently delete a trashed session and all its answers."""
    session = get_object_or_404(SurveySession, id=session_id, survey=request.survey, is_deleted=True)
    svc = SessionValidationService()
    svc.hard_delete(session)
    return HttpResponse(status=204, headers={'HX-Trigger': 'sessionDeleted'})


def _parse_bulk_session_ids(request, survey):
    """Parse JSON body and return list of SurveySession objects for the given IDs."""
    try:
        body = json.loads(request.body)
        ids = body.get('session_ids', [])
    except (json.JSONDecodeError, AttributeError):
        return []
    if not isinstance(ids, list):
        return []
    return list(SurveySession.objects.filter(id__in=ids, survey=survey))


@survey_permission_required('editor')
@require_POST
def analytics_bulk_set_status(request, survey_uuid):
    """Bulk set validation_status on multiple sessions."""
    from django.db import transaction
    sessions = _parse_bulk_session_ids(request, request.survey)
    try:
        body = json.loads(request.body)
        status = body.get('status', '')
    except (json.JSONDecodeError, AttributeError):
        return HttpResponse(status=400)
    svc = SessionValidationService()
    try:
        with transaction.atomic():
            for s in sessions:
                svc.set_status(s, status)
    except ValueError:
        return HttpResponse(status=400)
    return HttpResponse(status=204, headers={'HX-Trigger': 'bulkActionDone'})


@survey_permission_required('editor')
@require_POST
def analytics_bulk_trash(request, survey_uuid):
    """Bulk soft-delete multiple sessions."""
    from django.db import transaction
    sessions = _parse_bulk_session_ids(request, request.survey)
    svc = SessionValidationService()
    with transaction.atomic():
        for s in sessions:
            if not s.is_deleted:
                svc.trash(s)
    return HttpResponse(status=204, headers={'HX-Trigger': 'bulkActionDone'})


@survey_permission_required('editor')
@require_POST
def analytics_bulk_restore(request, survey_uuid):
    """Bulk restore multiple trashed sessions."""
    from django.db import transaction
    sessions = _parse_bulk_session_ids(request, request.survey)
    svc = SessionValidationService()
    with transaction.atomic():
        for s in sessions:
            if s.is_deleted:
                svc.restore(s)
    return HttpResponse(status=204, headers={'HX-Trigger': 'bulkActionDone'})


@survey_permission_required('editor')
@require_POST
def analytics_bulk_hard_delete(request, survey_uuid):
    """Bulk permanently delete multiple trashed sessions."""
    from django.db import transaction
    sessions = _parse_bulk_session_ids(request, request.survey)
    svc = SessionValidationService()
    with transaction.atomic():
        for s in sessions:
            if s.is_deleted:
                svc.hard_delete(s)
    return HttpResponse(status=204, headers={'HX-Trigger': 'bulkActionDone'})


_ALLOWED_CLIENT_EVENTS = {'page_load', 'page_leave'}


@csrf_exempt
@require_POST
def analytics_track_event(request):
    """Public fire-and-forget endpoint for client-side events (page_load, page_leave).

    Security: session_id validated against request.session.
    Rate limited to 20 events/hour/survey_session via Django cache.
    """
    content_type = request.content_type or ''
    if 'application/json' not in content_type:
        return JsonResponse({'error': 'bad content-type'}, status=400)

    try:
        body = json.loads(request.body)
        client_session_id = int(body['session_id'])
        event_type = str(body.get('event_type', ''))
        section_name = str(body.get('section_name', ''))[:100]
    except (KeyError, ValueError, TypeError, json.JSONDecodeError):
        return JsonResponse({'error': 'bad payload'}, status=400)

    if event_type not in _ALLOWED_CLIENT_EVENTS:
        return JsonResponse({'error': 'invalid event_type'}, status=400)

    # Validate session ownership via server session.
    # Fall back to DB lookup for page_leave — the thanks page may have
    # already cleared survey_session_id before the beacon arrives.
    server_session_id = request.session.get('survey_session_id')
    if server_session_id and server_session_id != client_session_id:
        return JsonResponse({}, status=204)
    if not server_session_id and not SurveySession.objects.filter(pk=client_session_id).exists():
        return JsonResponse({}, status=204)

    # Rate limit keyed on survey_session_id
    rl_key = f"evt_rl_{client_session_id}"
    count = cache.get(rl_key, 0)
    if count >= 20:
        return JsonResponse({}, status=429)
    cache.set(rl_key, count + 1, 3600)

    # Build metadata based on event type
    metadata = {'section_name': section_name}
    if event_type == 'page_load':
        try:
            load_ms = int(body['load_ms'])
        except (KeyError, ValueError, TypeError):
            return JsonResponse({'error': 'bad payload'}, status=400)
        if load_ms <= 0 or load_ms > 120_000:
            return JsonResponse({'error': 'invalid timing'}, status=400)
        metadata['load_ms'] = load_ms
    elif event_type == 'page_leave':
        try:
            time_on_page_ms = int(body.get('time_on_page_ms', 0))
        except (ValueError, TypeError):
            time_on_page_ms = 0
        if 0 < time_on_page_ms <= 3_600_000:  # cap at 1 hour
            metadata['time_on_page_ms'] = time_on_page_ms

    try:
        session = SurveySession.objects.get(pk=client_session_id)
        emit_event(session, event_type, metadata)
    except SurveySession.DoesNotExist:
        pass

    return JsonResponse({}, status=204)
