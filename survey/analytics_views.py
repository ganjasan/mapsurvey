import json

from django.shortcuts import render, get_object_or_404

from .models import Question
from .permissions import survey_permission_required
from .analytics import SurveyAnalyticsService


@survey_permission_required('viewer')
def analytics_dashboard(request, survey_uuid):
    """Full analytics dashboard page for a survey."""
    survey = request.survey
    service = SurveyAnalyticsService(survey)

    overview = service.get_overview()
    daily = service.get_daily_sessions()
    geo_collection = service.get_geo_feature_collection()
    question_stats = service.get_all_question_stats()

    return render(request, 'editor/analytics_dashboard.html', {
        'survey': survey,
        'total_sessions': overview['total_sessions'],
        'completed_count': overview['completed_count'],
        'completion_rate': overview['completion_rate'],
        'daily_data_json': json.dumps(daily),
        'geo_json': json.dumps(geo_collection),
        'geo_features_count': len(geo_collection['features']),
        'question_stats': question_stats,
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

    result = service.get_text_answers(question, page=page, page_size=page_size)

    return render(request, 'editor/partials/analytics_text_answers.html', {
        'survey': survey,
        'question': question,
        **result,
    })
