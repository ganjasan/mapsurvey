"""End-to-end tests for survey creation and core settings (EC-01, ES-02)."""
import uuid

import pytest

from survey.models import SurveyHeader, SurveySection, SurveySession


@pytest.fixture
def created_survey_name():
    name = f"e2e-create-{uuid.uuid4().hex[:8]}"
    yield name
    survey = SurveyHeader.objects.filter(name=name).first()
    if survey:
        SurveySession.objects.filter(survey=survey).delete()
        survey.delete()


def test_survey_create_form_creates_header_and_default_section(
    logged_in_page, base_url, created_survey_name
):
    """
    EC-01.

    GIVEN an authenticated owner on the New Survey page
    WHEN the form is submitted with a unique name and default settings
    THEN a SurveyHeader is created with that name + auto UUID, exactly one
        head section is appended, and the browser lands on the editor.
    """
    logged_in_page.goto(f"{base_url}/editor/surveys/new/")
    logged_in_page.wait_for_load_state("networkidle")

    logged_in_page.fill('input[name="name"]', created_survey_name)
    # ``visibility`` and ``redirect_url`` keep their pre-filled defaults.
    logged_in_page.get_by_role("button", name="Create Survey").click()
    logged_in_page.wait_for_url(
        lambda url: "/editor/surveys/" in url and "/new/" not in url
    )

    survey = SurveyHeader.objects.filter(name=created_survey_name).first()
    assert survey is not None, "SurveyHeader was not persisted"
    assert survey.uuid is not None, "Survey UUID auto-generation failed"
    assert str(survey.uuid) in logged_in_page.url, (
        "Editor URL does not contain the new survey UUID"
    )

    head_sections = SurveySection.objects.filter(
        survey_header=survey, is_head=True
    )
    assert head_sections.count() == 1, (
        "Expected exactly one head section after creation, "
        f"got {head_sections.count()}"
    )


def test_visibility_setting_persists(
    logged_in_page, base_url, draft_survey
):
    """
    ES-02.

    GIVEN a draft survey owned by the logged-in user
    WHEN the owner toggles visibility from "private" to "public" in settings
    THEN ``SurveyHeader.visibility`` is updated to "public" in the DB.
    """
    survey = draft_survey
    survey.visibility = "private"
    survey.save(update_fields=["visibility"])

    logged_in_page.goto(f"{base_url}/editor/surveys/{survey.uuid}/settings/")
    logged_in_page.wait_for_load_state("networkidle")

    visibility_select = logged_in_page.locator('select[name="visibility"]').first
    assert visibility_select.count() > 0, "visibility <select> not on settings page"
    visibility_select.select_option("public")

    # Submit the settings form
    logged_in_page.get_by_role("button", name="Save Settings").click()
    logged_in_page.wait_for_load_state("networkidle")

    survey.refresh_from_db()
    assert survey.visibility == "public", (
        f"visibility did not persist; still {survey.visibility!r}"
    )
