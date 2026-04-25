"""End-to-end tests for the respondent flow (RL-01..03, RN-04, QT-01..04, TH-01/04).

These tests drive an unauthenticated browser against published surveys.
"""
import uuid

import pytest

from survey.models import Answer, Question, SurveyHeader, SurveySection, SurveySession


@pytest.fixture
def multilingual_survey(test_user):
    from tests_e2e.conftest import _build_survey, _purge_survey

    survey = _build_survey(
        name=f"e2e-multi-{uuid.uuid4().hex[:6]}",
        basemaps=["streets"],
        owner=test_user,
        sections_count=1,
        add_point=False,
    )
    survey.available_languages = ["en", "ru"]
    survey.save(update_fields=["available_languages"])
    yield survey
    _purge_survey(survey)


@pytest.fixture
def survey_with_mixed_questions(test_user):
    from tests_e2e.conftest import _build_survey, _purge_survey

    survey = _build_survey(
        name=f"e2e-mix-{uuid.uuid4().hex[:6]}",
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
        code="Q_TEXT",
        required=True,
    )
    Question.objects.create(
        survey_section=section,
        name="Your age?",
        input_type="number",
        order_number=2,
        code="Q_NUM",
        required=True,
    )
    Question.objects.create(
        survey_section=section,
        name="Bike commuter?",
        input_type="choice",
        order_number=3,
        code="Q_CHOICE",
        required=True,
        choices=[
            {"code": 1, "name": "Yes"},
            {"code": 2, "name": "No"},
        ],
    )
    Question.objects.create(
        survey_section=section,
        name="Favorite modes?",
        input_type="multichoice",
        order_number=4,
        code="Q_MULTI",
        required=False,
        choices=[
            {"code": 10, "name": "Bus"},
            {"code": 20, "name": "Tram"},
            {"code": 30, "name": "Bike"},
        ],
    )
    yield survey
    _purge_survey(survey)


def test_multilingual_redirects_to_language_picker(
    page, base_url, multilingual_survey
):
    """
    RL-01.

    GIVEN a published multilingual survey with available_languages=["en", "ru"]
    WHEN an anonymous respondent opens /surveys/<uuid>/
    THEN they land on /surveys/<uuid>/language/.
    """
    survey = multilingual_survey
    page.goto(f"{base_url}/surveys/{survey.uuid}/")
    page.wait_for_load_state("networkidle")
    assert page.url.endswith("/language/"), (
        f"Expected redirect to language picker, landed on {page.url}"
    )


def test_single_language_survey_skips_language_picker(
    page, base_url, survey_with_mixed_questions
):
    """
    RL-02.

    GIVEN a published survey with no available_languages configured
    WHEN an anonymous respondent opens /surveys/<uuid>/
    THEN they go straight to /surveys/<uuid>/section_1/.
    """
    survey = survey_with_mixed_questions
    page.goto(f"{base_url}/surveys/{survey.uuid}/")
    page.wait_for_load_state("networkidle")
    assert "/language/" not in page.url, (
        f"Single-language survey should not show language picker; got {page.url}"
    )
    assert "/section_1" in page.url, (
        f"Expected to land on first section, got {page.url}"
    )


def test_language_choice_persists_to_session(page, base_url, multilingual_survey):
    """
    RL-03.

    GIVEN a respondent on the language picker
    WHEN they click an available language
    THEN the SurveySession.language column reflects that code.
    """
    survey = multilingual_survey
    page.goto(f"{base_url}/surveys/{survey.uuid}/language/")
    page.wait_for_load_state("networkidle")

    page.locator('a[href*="lang=en"], button:has-text("English")').first.click()
    page.wait_for_load_state("networkidle")

    sessions = SurveySession.objects.filter(survey=survey).order_by("-id")
    assert sessions.exists(), "No SurveySession created"
    assert sessions.first().language == "en", (
        f"Session language not stored; got {sessions.first().language!r}"
    )


def test_submit_answers_persist_for_each_type(
    page, base_url, survey_with_mixed_questions
):
    """
    QT-01..04.

    GIVEN a single-section survey with text_line, number, choice, multichoice
    WHEN the respondent fills the form and clicks Next
    THEN one Answer row exists per non-empty question and the redirect lands
        on the thanks page (since this is the last section).
    """
    survey = survey_with_mixed_questions
    section = SurveySection.objects.get(survey_header=survey, is_head=True)

    page.goto(f"{base_url}/surveys/{survey.uuid}/")
    page.wait_for_url(lambda u: "/section_1" in u)

    page.fill('input[name="Q_TEXT"]', "Alice")
    page.fill('input[name="Q_NUM"]', "30")
    # The actual <input type="radio|checkbox"> is visually hidden via CSS;
    # the surrounding <label> is the click target.
    page.locator('label:has(input[name="Q_CHOICE"][value="1"])').click()
    page.locator('label:has(input[name="Q_MULTI"][value="20"])').click()
    page.locator('label:has(input[name="Q_MULTI"][value="30"])').click()

    page.locator("input.next_button[type=submit]").first.click()
    page.wait_for_load_state("networkidle")

    if "/thanks/" not in page.url:
        # Surface form errors so the assertion message is useful
        errors = page.locator(".errorlist, .alert, .text-danger").all_inner_texts()
        radio_state = page.evaluate(
            """() => Array.from(
                document.querySelectorAll('input[name=\"Q_CHOICE\"]')
            ).map(i => ({value: i.value, checked: i.checked}))"""
        )
        raise AssertionError(
            f"Expected thanks redirect, landed on {page.url}; "
            f"errors={errors!r}; radios={radio_state!r}"
        )

    sessions = SurveySession.objects.filter(survey=survey).order_by("-id")
    assert sessions.exists(), "No SurveySession created"
    sess = sessions.first()
    answers = Answer.objects.filter(survey_session=sess, question__survey_section=section)
    by_code = {a.question.code: a for a in answers}

    assert by_code["Q_TEXT"].text == "Alice"
    assert by_code["Q_NUM"].numeric == 30
    assert by_code["Q_CHOICE"].selected_choices == [1]
    assert sorted(by_code["Q_MULTI"].selected_choices) == [20, 30]


def test_thanks_page_clears_survey_session_cookie(
    page, base_url, survey_with_mixed_questions
):
    """
    TH-04.

    GIVEN a respondent has just submitted the last section
    WHEN they land on the thanks page
    THEN the survey_session_id key is removed from the Django session cookie.
    """
    survey = survey_with_mixed_questions

    page.goto(f"{base_url}/surveys/{survey.uuid}/")
    page.wait_for_url(lambda u: "/section_1" in u)
    page.fill('input[name="Q_TEXT"]', "Alice")
    page.fill('input[name="Q_NUM"]', "1")
    page.locator('label:has(input[name="Q_CHOICE"][value="1"])').click()
    page.locator("input.next_button[type=submit]").first.click()
    page.wait_for_url(lambda u: "/thanks/" in u)

    # Session cookie itself stays (it's the Django session), but the
    # ``survey_session_id`` key inside it must have been deleted by the view.
    page.goto(f"{base_url}/editor/")  # any view that reads request.session
    cookies = page.context.cookies()
    sessionid = next((c["value"] for c in cookies if c["name"] == "sessionid"), None)
    assert sessionid is not None, "Django sessionid cookie missing after thanks page"

    # Decode the session via Django to assert the key is gone
    from django.contrib.sessions.models import Session
    session = Session.objects.filter(session_key=sessionid).first()
    assert session is not None, "Session row missing in DB"
    data = session.get_decoded()
    assert "survey_session_id" not in data, (
        "survey_session_id key was not removed by the thanks view"
    )
