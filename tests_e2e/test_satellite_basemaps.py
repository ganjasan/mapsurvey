"""End-to-end tests for the satellite/topo basemap feature.

GIVEN a published survey configured with all three basemaps
WHEN a respondent opens the survey
THEN every basemap tile URL is referenced and the layer switcher renders.
"""
import re


def test_satellite_basemap_renders_in_respondent_page(
    page, base_url, survey_with_all_basemaps
):
    """
    GIVEN a published survey with basemaps=["streets", "satellite", "topo"]
    WHEN the respondent visits its first section
    THEN the page HTML references both the satellite and topo tile providers
        and the basemap layer switcher renders in the DOM.
    """
    survey = survey_with_all_basemaps
    page.goto(f"{base_url}/surveys/{survey.uuid}/")

    page.wait_for_load_state("networkidle")
    html = page.content()

    assert re.search(r"Esri\.WorldImagery|arcgisonline.*World_Imagery", html), (
        "satellite tile URL not present in respondent page"
    )
    assert re.search(r"opentopomap|OpenTopoMap", html, re.IGNORECASE), (
        "topo tile URL not present in respondent page"
    )

    layer_control = page.locator(".leaflet-control-layers")
    assert layer_control.count() > 0, "Leaflet layer switcher control not found"


def test_basemap_settings_visible_for_owner(
    logged_in_page, base_url, survey_with_all_basemaps
):
    """
    GIVEN a survey owned by the logged-in user
    WHEN the owner opens its settings page
    THEN the basemap checkboxes are present.
    """
    survey = survey_with_all_basemaps
    logged_in_page.goto(f"{base_url}/editor/surveys/{survey.uuid}/settings/")
    logged_in_page.wait_for_load_state("networkidle")

    body_text = logged_in_page.locator("body").inner_text().lower()
    assert "satellite" in body_text, "settings page does not mention satellite basemap"
    assert "topo" in body_text or "topographic" in body_text, (
        "settings page does not mention topographic basemap"
    )
