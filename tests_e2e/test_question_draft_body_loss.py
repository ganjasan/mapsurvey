"""End-to-end check for the draft-question body-loss fix (change
fix-draft-question-body-loss, backlog #179).

The defect lived in the browser: the modal's `hidden.bs.modal` handler posted
`if_empty=1` for any draft with an empty Name, so a Formatted Text block whose
whole content sits in Subtext was deleted on close. Django's test client cannot
see that handler at all, which is why this lives here.
"""
from survey.models import Question, SurveySection

# `draft_survey` is listed FIRST on purpose: on a pristine dev database /editor/
# redirects while the workspace has no survey, and the login fixture's
# wait_for_url('/editor/') then times out (lesson_e2e_needs_a_seeded_org).


def _wait_modal_settled(page):
    """Bootstrap ignores hide() and Escape while the show transition runs."""
    page.wait_for_function(
        "() => { const m = $('#questionModal').data('bs.modal');"
        " return m && m._isShown && !m._isTransitioning; }"
    )


def _open_new_question_modal(page, base_url, survey):
    page.goto(f"{base_url}/editor/surveys/{survey.uuid}/")
    page.wait_for_selector("#section-form")
    # NOT just `.add-question-btn`: a geo question renders "+ Add Sub-question"
    # with the same class, so a bare selector opens the sub-question form instead.
    page.click("#editor-main .add-question-btn:not(.add-question-btn--sub)")
    page.wait_for_selector("#questionModalBody .qtp-card", state="visible")
    _wait_modal_settled(page)


def _close_create_modal(page):
    """Close the modal while it is still in create mode (no type picked yet).

    Escape, with focus inside the dialog — the same gesture a creator uses. The
    modal must have finished its show transition first, or Bootstrap swallows it.
    """
    page.focus("form[data-create-picker] [name=name]")
    page.keyboard.press("Escape")
    page.wait_for_selector("#questionModal", state="hidden")
    # The close handler posts the draft via htmx; give it a round trip.
    page.wait_for_timeout(1500)


def _close_modal(page):
    # Escape, with focus put inside the dialog first: Bootstrap's keyboard
    # dismiss only fires from within, and clicking the × is unreliable here
    # because the live-preview pane re-renders on a timer, so Playwright's
    # actionability check never settles.
    page.focus("form[data-draft-question] [name=name]")
    page.keyboard.press("Escape")
    page.wait_for_selector("#questionModal", state="hidden")
    # The close handler deletes via fetch; give it a round trip.
    page.wait_for_timeout(1500)


def test_formatted_text_block_survives_close_without_a_name(draft_survey, logged_in_page, base_url):
    """
    GIVEN the New Question modal with Formatted Text picked and a body typed into Content
    WHEN the creator closes the modal without ever filling Name
    THEN the question is still in the section with its body intact
    """
    survey = draft_survey
    section = SurveySection.objects.get(survey_header=survey, is_head=True)
    before = set(Question.objects.filter(survey_section=section).values_list("pk", flat=True))

    _open_new_question_modal(logged_in_page, base_url, survey)
    logged_in_page.click('.qtp-card[data-qtp-value="html"]')
    logged_in_page.wait_for_selector("form[data-draft-question]")
    logged_in_page.wait_for_selector("#html-body-quill .ql-editor", state="visible")

    logged_in_page.click("#html-body-quill .ql-editor")
    logged_in_page.keyboard.type("Takes about 5 minutes.")
    # The Quill handler mirrors into the posted input only on user input.
    assert logged_in_page.input_value("form[data-draft-question] [name=subtext]").strip()

    _close_modal(logged_in_page)

    created = Question.objects.filter(survey_section=section).exclude(pk__in=before)
    assert created.count() == 1, "the Formatted Text draft was deleted on close"
    q = created.get()
    assert (q.name or "") == ""
    assert "Takes about 5 minutes." in q.subtext


def test_untouched_draft_is_still_discarded_on_close(draft_survey, logged_in_page, base_url):
    """
    GIVEN the New Question modal with a type picked and nothing typed anywhere
    WHEN the creator closes the modal
    THEN the draft row is gone, so abandoned picks still do not litter the section
    """
    survey = draft_survey
    section = SurveySection.objects.get(survey_header=survey, is_head=True)
    before = set(Question.objects.filter(survey_section=section).values_list("pk", flat=True))

    _open_new_question_modal(logged_in_page, base_url, survey)
    logged_in_page.click('.qtp-card[data-qtp-value="text"]')
    logged_in_page.wait_for_selector("form[data-draft-question]")

    _close_modal(logged_in_page)

    assert not Question.objects.filter(survey_section=section).exclude(pk__in=before).exists()


def _type_without_picking(page, base_url, survey, name):
    _open_new_question_modal(page, base_url, survey)
    page.fill("form[data-create-picker] [name=name]", name)


def test_closing_before_a_type_is_picked_keeps_the_text_as_a_text_question(
    draft_survey, logged_in_page, base_url
):
    """
    GIVEN the New Question modal with a name typed but no type picked, so no row exists yet
    WHEN the creator closes the modal
    THEN the words are kept as a text question instead of being dropped silently
    """
    section = SurveySection.objects.get(survey_header=draft_survey, is_head=True)
    before = set(Question.objects.filter(survey_section=section).values_list("pk", flat=True))

    _type_without_picking(logged_in_page, base_url, draft_survey, "Where do you park?")
    _close_create_modal(logged_in_page)

    created = Question.objects.filter(survey_section=section).exclude(pk__in=before)
    assert created.count() == 1, "the typed question was lost on close"
    q = created.get()
    assert (q.name, q.input_type) == ("Where do you park?", "text")


def test_closing_an_untouched_new_question_modal_creates_nothing(
    draft_survey, logged_in_page, base_url
):
    """
    GIVEN the New Question modal opened and nothing typed anywhere
    WHEN the creator closes it
    THEN no row is created, so an idle open still leaves the section alone
    """
    section = SurveySection.objects.get(survey_header=draft_survey, is_head=True)
    before = set(Question.objects.filter(survey_section=section).values_list("pk", flat=True))

    _open_new_question_modal(logged_in_page, base_url, draft_survey)
    _close_create_modal(logged_in_page)

    assert not Question.objects.filter(survey_section=section).exclude(pk__in=before).exists()
