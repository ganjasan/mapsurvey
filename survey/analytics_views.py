import json

from django.db.models import Q
from django.shortcuts import render, get_object_or_404

from .models import Question, Answer, SurveySession
from .permissions import survey_permission_required
from .analytics import SurveyAnalyticsService


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

    return render(request, 'editor/analytics_dashboard.html', {
        'survey': survey,
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

    answers = (
        Answer.objects
        .filter(survey_session=session, parent_answer_id__isnull=True)
        .select_related('question', 'question__survey_section')
        .order_by('question__survey_section__id', 'question__order_number')
    )

    answer_rows = []
    geo_features = []
    for a in answers:
        q = a.question
        if q.input_type in ('choice', 'multichoice', 'rating'):
            value = ', '.join(a.get_selected_choice_names()) or '\u2014'
        elif q.input_type in ('number', 'range'):
            value = str(a.numeric) if a.numeric is not None else '\u2014'
        elif q.input_type in ('text', 'text_line', 'datetime'):
            value = a.text or '\u2014'
        elif q.input_type in ('point', 'line', 'polygon'):
            geom = a.point or a.line or a.polygon
            if geom:
                geo_features.append({
                    'type': 'Feature',
                    'geometry': json.loads(geom.geojson),
                    'properties': {'question': q.name, 'type': q.input_type},
                })
                value = q.input_type + ' feature'
            else:
                value = '\u2014'
        else:
            value = '\u2014'

        answer_rows.append({
            'question_name': q.name,
            'section_name': q.survey_section.title or q.survey_section.name,
            'input_type': q.input_type,
            'value': value,
        })

    return render(request, 'editor/partials/analytics_session_detail.html', {
        'survey': survey,
        'session': session,
        'answer_rows': answer_rows,
        'geo_json': json.dumps({'type': 'FeatureCollection', 'features': geo_features}),
        'has_geo': bool(geo_features),
    })
