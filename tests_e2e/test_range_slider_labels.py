"""End-to-end test for range slider tick marks and from-to labels."""


def test_range_slider_renders_first_and_last_choice_labels(
    page, base_url, survey_with_range_question
):
    """
    GIVEN a published survey with a range question whose first/last choices
        have non-empty labels ("Very poor" / "Excellent")
    WHEN the respondent opens the section containing the range question
    THEN both labels are rendered alongside the slider, and the tick container
        renders one tick per choice.
    """
    survey = survey_with_range_question
    page.goto(f"{base_url}/surveys/{survey.uuid}/")
    page.wait_for_load_state("networkidle")

    body_text = page.locator("body").inner_text()
    assert "Very poor" in body_text, "first choice label missing from page"
    assert "Excellent" in body_text, "last choice label missing from page"

    ticks = page.locator(".range-ticks span")
    assert ticks.count() == 5, (
        f"expected 5 tick marks for 5 choices, got {ticks.count()}"
    )

    labels_block = page.locator(".range-labels")
    assert labels_block.count() == 1, (
        "range labels container (.range-labels) not rendered"
    )
