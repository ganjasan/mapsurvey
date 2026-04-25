"""End-to-end tests for answer prepopulation on back-navigation (AP-01, AP-02)."""
import uuid

import pytest

from survey.models import Question, SurveyHeader, SurveySection, SurveySession


@pytest.fixture
def two_section_survey(test_user):
    from tests_e2e.conftest import _build_survey, _purge_survey

    survey = _build_survey(
        name=f"e2e-prepop-{uuid.uuid4().hex[:6]}",
        basemaps=["streets"],
        owner=test_user,
        sections_count=2,
        add_point=False,
    )
    section1 = SurveySection.objects.get(survey_header=survey, is_head=True)
    Question.objects.create(
        survey_section=section1,
        name="Your name?",
        input_type="text_line",
        order_number=1,
        code="Q_T",
        required=True,
    )
    Question.objects.create(
        survey_section=section1,
        name="Your age?",
        input_type="number",
        order_number=2,
        code="Q_N",
        required=True,
    )
    Question.objects.create(
        survey_section=section1,
        name="Bike commuter?",
        input_type="choice",
        order_number=3,
        code="Q_C",
        required=True,
        choices=[
            {"code": 1, "name": "Yes"},
            {"code": 2, "name": "No"},
        ],
    )
    Question.objects.create(
        survey_section=section1,
        name="Modes you use",
        input_type="multichoice",
        order_number=4,
        code="Q_M",
        required=False,
        choices=[
            {"code": 10, "name": "Bus"},
            {"code": 20, "name": "Tram"},
            {"code": 30, "name": "Bike"},
        ],
    )
    yield survey
    _purge_survey(survey)


def test_text_and_number_fields_prepopulate_on_back(
    page, base_url, two_section_survey
):
    """
    AP-01.

    GIVEN a respondent submitted section 1 with text + number answers
    WHEN they click "Back" from section 2
    THEN the text input and number input render with their saved values.
    """
    survey = two_section_survey

    page.goto(f"{base_url}/surveys/{survey.uuid}/")
    page.wait_for_url(lambda u: "/section_1" in u)

    page.fill('input[name="Q_T"]', "Alice")
    page.fill('input[name="Q_N"]', "30")
    page.locator('label:has(input[name="Q_C"][value="1"])').click()
    # HTMX submit swaps the section content in place; the URL does not change.
    with page.expect_response(
        lambda r: f"/surveys/{survey.uuid}/section_1/" in r.url
        and r.request.method == "POST"
    ):
        page.locator("input.next_button[type=submit]").first.click()
    page.wait_for_load_state("networkidle")

    # Reopen section 1 via direct GET — the view should prepopulate from
    # the answers stored in the active SurveySession.
    page.goto(f"{base_url}/surveys/{survey.uuid}/section_1/")
    page.wait_for_load_state("networkidle")

    assert page.input_value('input[name="Q_T"]') == "Alice", (
        "text_line input did not prepopulate"
    )
    # The numeric field is stored as a Decimal so the input value may be
    # rendered as "30.0"; comparing as float keeps the test robust.
    assert float(page.input_value('input[name="Q_N"]')) == 30.0, (
        "number input did not prepopulate"
    )


def test_choice_and_multichoice_prepopulate_on_back(
    page, base_url, two_section_survey
):
    """
    AP-02.

    GIVEN a respondent submitted section 1 with one radio + two checkboxes
    WHEN they click "Back" from section 2
    THEN the same radio is pre-selected and the same checkboxes are pre-checked.
    """
    survey = two_section_survey

    page.goto(f"{base_url}/surveys/{survey.uuid}/")
    page.wait_for_url(lambda u: "/section_1" in u)

    page.fill('input[name="Q_T"]', "Bob")
    page.fill('input[name="Q_N"]', "42")
    page.locator('label:has(input[name="Q_C"][value="2"])').click()
    page.locator('label:has(input[name="Q_M"][value="10"])').click()
    page.locator('label:has(input[name="Q_M"][value="30"])').click()
    with page.expect_response(
        lambda r: f"/surveys/{survey.uuid}/section_1/" in r.url
        and r.request.method == "POST"
    ):
        page.locator("input.next_button[type=submit]").first.click()
    page.wait_for_load_state("networkidle")

    page.goto(f"{base_url}/surveys/{survey.uuid}/section_1/")
    page.wait_for_load_state("networkidle")

    radio_state = page.evaluate(
        """() => Array.from(
            document.querySelectorAll('input[name="Q_C"]')
        ).find(i => i.checked)?.value || ''"""
    )
    assert radio_state == "2", f"Radio not prepopulated; got {radio_state!r}"

    checked_modes = page.evaluate(
        """() => Array.from(
            document.querySelectorAll('input[name="Q_M"]')
        ).filter(i => i.checked).map(i => i.value).sort()"""
    )
    assert checked_modes == ["10", "30"], (
        f"Multichoice did not prepopulate; got {checked_modes!r}"
    )
