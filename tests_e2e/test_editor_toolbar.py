"""Editor toolbar / chrome tests."""


def test_settings_link_present_in_editor_toolbar(
    logged_in_page, base_url, survey_with_all_basemaps
):
    """
    GIVEN a survey owned by the logged-in user
    WHEN they open the editor for the survey
    THEN the toolbar links to the survey's settings page.
    """
    survey = survey_with_all_basemaps
    logged_in_page.goto(f"{base_url}/editor/surveys/{survey.uuid}/")
    logged_in_page.wait_for_load_state("networkidle")

    settings_link = logged_in_page.locator(
        f'a[href="/editor/surveys/{survey.uuid}/settings/"]'
    )
    assert settings_link.count() >= 1, (
        "Settings link not found in editor toolbar"
    )


def test_cover_gradient_is_deterministic_across_reloads(
    logged_in_page, base_url, survey_with_all_basemaps
):
    """
    GIVEN a survey listed on the dashboard
    WHEN the dashboard is loaded twice
    THEN the inline gradient style for that survey card is identical.
    """
    survey = survey_with_all_basemaps
    survey_name = survey.name

    logged_in_page.goto(f"{base_url}/editor/")
    logged_in_page.wait_for_load_state("networkidle")
    first = logged_in_page.evaluate(
        f"""(name) => {{
            const cards = document.querySelectorAll('[style*=\"linear-gradient\"]');
            for (const c of cards) {{
                if (c.innerText && c.innerText.includes(name))
                    return c.getAttribute('style');
                const parent = c.closest('a, .survey-card, .card');
                if (parent && parent.innerText.includes(name))
                    return c.getAttribute('style');
            }}
            return '';
        }}""",
        survey_name,
    )
    assert first, f"could not locate gradient for survey {survey_name}"

    logged_in_page.reload()
    logged_in_page.wait_for_load_state("networkidle")
    second = logged_in_page.evaluate(
        f"""(name) => {{
            const cards = document.querySelectorAll('[style*=\"linear-gradient\"]');
            for (const c of cards) {{
                if (c.innerText && c.innerText.includes(name))
                    return c.getAttribute('style');
                const parent = c.closest('a, .survey-card, .card');
                if (parent && parent.innerText.includes(name))
                    return c.getAttribute('style');
            }}
            return '';
        }}""",
        survey_name,
    )
    assert second == first, (
        "Cover gradient changed across reloads — hash() determinism regressed"
    )
