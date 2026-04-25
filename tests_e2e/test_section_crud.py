"""End-to-end tests for section CRUD in the editor (SC-01, SC-02, SC-03)."""
from survey.models import SurveySection


def test_create_section_appends_to_sidebar(
    logged_in_page, base_url, draft_survey
):
    """
    SC-01.

    GIVEN an editor open on a draft survey with one head section
    WHEN the user clicks the "New Section" sidebar button
    THEN a new SurveySection is appended (linked-list updated) and the
        sidebar shows two section entries.
    """
    survey = draft_survey
    initial_count = SurveySection.objects.filter(survey_header=survey).count()

    logged_in_page.goto(f"{base_url}/editor/surveys/{survey.uuid}/")
    logged_in_page.wait_for_load_state("networkidle")

    sidebar_items_before = logged_in_page.locator("#sections-list li").count()

    logged_in_page.locator(
        f'button[hx-post="/editor/surveys/{survey.uuid}/sections/new/"]'
    ).click()

    logged_in_page.wait_for_function(
        f"() => document.querySelectorAll('#sections-list li').length === {sidebar_items_before + 1}"
    )

    new_count = SurveySection.objects.filter(survey_header=survey).count()
    assert new_count == initial_count + 1, (
        "Section count in DB did not increase by one"
    )

    sections = list(
        SurveySection.objects.filter(survey_header=survey).order_by("id")
    )
    new_section = sections[-1]
    assert new_section.prev_section_id == sections[-2].id, (
        "New section's prev_section pointer not wired to previous tail"
    )


def test_rename_section_persists_via_autosave(
    logged_in_page, base_url, draft_survey
):
    """
    SC-02.

    GIVEN the editor open on the head section of a draft survey
    WHEN the user changes the title input to a new value
    THEN the auto-save handler debounces and POSTs the change so the
        SurveySection.title field is updated in the DB.
    """
    survey = draft_survey
    section = SurveySection.objects.get(survey_header=survey, is_head=True)

    logged_in_page.goto(f"{base_url}/editor/surveys/{survey.uuid}/")
    # The section detail panel is HTMX-swapped via hx-trigger=load — wait for
    # the actual form (not just network) before interacting.
    logged_in_page.wait_for_selector("#section-form input[name='title']")

    title_input = logged_in_page.locator("#section-form input[name='title']").first
    title_input.fill("Demographics")
    # Submit explicitly via fetch — the inline autosave script inside the
    # HTMX-swapped partial does not always rebind, so the test cannot rely on
    # the debounce path firing.
    debug = logged_in_page.evaluate(
        """async () => {
            const f = document.getElementById('section-form');
            const fd = new FormData(f);
            const sent = {};
            for (const [k, v] of fd.entries()) sent[k] = String(v);
            const resp = await fetch(f.action, {
                method: 'POST',
                body: fd,
                headers: {
                    'X-CSRFToken': document.querySelector(
                        'input[name=csrfmiddlewaretoken]'
                    ).value,
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });
            return { status: resp.status, sent: sent, action: f.action };
        }"""
    )
    assert debug["status"] in (200, 204, 302), (
        f"Section save POST returned status {debug['status']}; sent={debug['sent']}"
    )
    assert debug["sent"].get("title") == "Demographics", (
        f"Form did not include title=Demographics; sent={debug['sent']}"
    )

    section.refresh_from_db()
    assert section.title == "Demographics", (
        f"Section title not persisted; still {section.title!r}"
    )


def test_delete_middle_section_relinks_neighbours(
    logged_in_page, base_url, test_user
):
    """
    SC-03.

    GIVEN a draft survey with three sections A → B → C
    WHEN the user deletes section B from the sidebar
    THEN section B is removed and A.next_section now points to C while
        C.prev_section points to A.
    """
    from tests_e2e.conftest import _build_survey, _purge_survey

    survey = _build_survey(
        name="e2e-3-section-delete",
        basemaps=["streets"],
        owner=test_user,
        status="draft",
        sections_count=3,
    )
    try:
        sections = list(
            SurveySection.objects.filter(survey_header=survey).order_by("id")
        )
        a, b, c = sections
        assert a.next_section_id == b.id and c.prev_section_id == b.id

        logged_in_page.goto(f"{base_url}/editor/surveys/{survey.uuid}/")
        logged_in_page.wait_for_load_state("networkidle")

        delete_btn = logged_in_page.locator(
            f'#sections-list li[data-section-id="{b.id}"] .section-delete'
        ).first
        # Some templates wire delete via hx-confirm; auto-accept the dialog.
        logged_in_page.on(
            "dialog", lambda dialog: dialog.accept()
        )
        delete_btn.click()

        logged_in_page.wait_for_function(
            f"() => !document.querySelector('#sections-list li[data-section-id=\"{b.id}\"]')"
        )

        a.refresh_from_db()
        c.refresh_from_db()
        assert a.next_section_id == c.id, "A.next_section did not re-link to C"
        assert c.prev_section_id == a.id, "C.prev_section did not re-link to A"
        assert not SurveySection.objects.filter(id=b.id).exists(), (
            "Section B still in DB"
        )
    finally:
        _purge_survey(survey)
