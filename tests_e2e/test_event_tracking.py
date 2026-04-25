"""End-to-end tests for survey event tracking (UT-01, UT-02)."""
import uuid

import pytest

from survey.models import Question, SurveyEvent, SurveySection, SurveySession


@pytest.fixture
def single_section_survey(test_user):
    from tests_e2e.conftest import _build_survey, _purge_survey

    survey = _build_survey(
        name=f"e2e-events-{uuid.uuid4().hex[:6]}",
        basemaps=["streets"],
        owner=test_user,
        sections_count=1,
        add_point=False,
    )
    section = SurveySection.objects.get(survey_header=survey, is_head=True)
    Question.objects.create(
        survey_section=section,
        name="Your name?",
        input_type="text_line",
        order_number=1,
        code="Q_NAME",
        required=False,
    )
    yield survey
    _purge_survey(survey)


def test_session_start_event_emitted_on_first_section_visit(
    page, base_url, single_section_survey
):
    """
    UT-01.

    GIVEN an anonymous respondent who has never started this survey
    WHEN they navigate to /surveys/<uuid>/ for the first time
    THEN a SurveySession is created and exactly one ``session_start``
        SurveyEvent row exists for that session.
    """
    survey = single_section_survey
    page.goto(f"{base_url}/surveys/{survey.uuid}/")
    page.wait_for_url(lambda u: "/section_1" in u)

    sessions = SurveySession.objects.filter(survey=survey).order_by("-id")
    assert sessions.exists(), "No SurveySession was created"
    sess = sessions.first()

    starts = SurveyEvent.objects.filter(session=sess, event_type="session_start")
    assert starts.count() == 1, (
        f"Expected exactly one session_start event; got {starts.count()}"
    )


def test_survey_complete_event_emitted_on_finish(
    page, base_url, single_section_survey
):
    """
    UT-02.

    GIVEN a single-section survey with one optional question
    WHEN the respondent submits the section
    THEN a ``survey_complete`` SurveyEvent row is recorded for the
        session in addition to the earlier ``session_start``.
    """
    survey = single_section_survey
    page.goto(f"{base_url}/surveys/{survey.uuid}/")
    page.wait_for_url(lambda u: "/section_1" in u)

    page.fill('input[name="Q_NAME"]', "Alice")
    page.locator("input.next_button[type=submit]").first.click()
    page.wait_for_load_state("networkidle")

    sessions = SurveySession.objects.filter(survey=survey).order_by("-id")
    sess = sessions.first()

    completes = SurveyEvent.objects.filter(session=sess, event_type="survey_complete")
    assert completes.count() == 1, (
        f"Expected one survey_complete event after final submit; got "
        f"{completes.count()}"
    )
