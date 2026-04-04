import json

from django.core.cache import cache
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import Question, Answer, SurveySession
from .permissions import survey_permission_required
from .analytics import SurveyAnalyticsService, PerformanceAnalyticsService
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
