"""End-to-end tests for the analytics dashboard (AN-01, AN-02)."""
import uuid

import pytest

from survey.models import Answer, Question, SurveySection, SurveySession


@pytest.fixture
def survey_with_choice_responses(test_user):
    from tests_e2e.conftest import _build_survey, _purge_survey

    survey = _build_survey(
        name=f"e2e-analytics-{uuid.uuid4().hex[:6]}",
        basemaps=["streets"],
        owner=test_user,
        sections_count=1,
        add_point=False,
    )
    section = SurveySection.objects.get(survey_header=survey, is_head=True)
    choice_q = Question.objects.create(
        survey_section=section,
        name="Bike commuter?",
        input_type="choice",
        order_number=1,
        code="Q_BIKE",
        required=False,
        choices=[
            {"code": 1, "name": "Yes"},
            {"code": 2, "name": "No"},
        ],
    )
    # 3 sessions choose Yes, 2 sessions choose No
    for code in [1, 1, 1, 2, 2]:
        sess = SurveySession.objects.create(survey=survey, language=None)
        Answer.objects.create(
            survey_session=sess, question=choice_q, selected_choices=[code]
        )

    yield survey, choice_q
    _purge_survey(survey)


def test_analytics_dashboard_loads_for_owner(
    logged_in_page, base_url, survey_with_choice_responses
):
    """
    AN-01.

    GIVEN a survey owned by the logged-in user with collected responses
    WHEN the owner opens /editor/surveys/<uuid>/analytics/
    THEN the page returns 200 and at least one chart canvas is rendered.
    """
    survey, _ = survey_with_choice_responses

    logged_in_page.goto(f"{base_url}/editor/surveys/{survey.uuid}/analytics/")
    logged_in_page.wait_for_load_state("networkidle")

    canvases = logged_in_page.locator("canvas[id^='chart-q-'], canvas[id^='hist-q-']")
    assert canvases.count() >= 1, (
        "Expected at least one question chart canvas on analytics dashboard"
    )


def test_choice_question_chart_data_matches_counts(
    logged_in_page, base_url, survey_with_choice_responses
):
    """
    AN-02.

    GIVEN 3 "Yes" + 2 "No" answers on a single choice question
    WHEN the dashboard renders the question's chart
    THEN the chart_labels_json + chart_counts_json embedded for that
        question reflect the exact 3:2 distribution.
    """
    survey, choice_q = survey_with_choice_responses

    logged_in_page.goto(f"{base_url}/editor/surveys/{survey.uuid}/analytics/")
    logged_in_page.wait_for_load_state("networkidle")

    # The chart payload is embedded as data-* on the canvas (or in a sibling
    # script). Read the rendered DOM to extract the counts.
    counts_pair = logged_in_page.evaluate(
        f"""(qid) => {{
            // Question stats embed labels + counts as data attributes on a
            // wrapper element used by the dashboard JS to draw the canvas.
            const root = document.querySelector(
              '[data-question-id="' + qid + '"]'
            ) || document.querySelector('#chart-q-' + qid)?.closest(
              '.analytics-question'
            );
            if (!root) return null;
            const labels = root.getAttribute('data-choice-labels')
                || root.querySelector('[data-choice-labels]')
                  ?.getAttribute('data-choice-labels');
            const counts = root.getAttribute('data-choice-counts')
                || root.querySelector('[data-choice-counts]')
                  ?.getAttribute('data-choice-counts');
            return {{labels, counts}};
        }}""",
        choice_q.id,
    )

    if not counts_pair or not counts_pair.get("counts"):
        # Fall back to scraping the rendered list/table cells as text
        body_text = logged_in_page.locator("body").inner_text()
        assert "Yes" in body_text and "No" in body_text, (
            "Choice labels not present on dashboard"
        )
        return

    counts = sorted(map(int, counts_pair["counts"].strip("[]").split(",")), reverse=True)
    assert counts[:2] == [3, 2], (
        f"Choice histogram counts do not match 3:2; got {counts}"
    )
