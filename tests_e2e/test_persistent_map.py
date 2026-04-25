"""End-to-end tests for the persistent map across HTMX section navigation.

The map element should not be re-created when navigating between sections;
the same DOM node persists, basemap selection survives the transition.
"""


def test_map_dom_node_survives_htmx_section_navigation(
    page, base_url, survey_with_all_basemaps
):
    """
    GIVEN a published survey with two sections and a point question
    WHEN the respondent navigates from section 1 to section 2 via HTMX
    THEN the persistent map's DOM node is the same element across the transition.
    """
    survey = survey_with_all_basemaps
    page.goto(f"{base_url}/surveys/{survey.uuid}/")
    page.wait_for_load_state("networkidle")

    map_id_before = page.evaluate(
        "() => document.querySelector('#map')?.id || ''"
    )
    assert map_id_before == "map", (
        "No persistent map element (#map) found on the first section"
    )

    # Mark a unique marker on the map node so we can detect re-creation
    page.evaluate(
        "() => { const m = document.querySelector('#map');"
        " if (m) m.dataset.persistMarker = 'sentinel'; }"
    )

    next_button = page.locator("input.next_button[type=submit], button.next_button").first
    next_button.click()
    page.wait_for_load_state("networkidle")

    sentinel = page.evaluate(
        "() => document.querySelector('#map')?.dataset.persistMarker || ''"
    )
    assert sentinel == "sentinel", (
        "Map DOM node was re-created during section navigation — sentinel lost"
    )
