"""End-to-end tests for question CRUD and inline choices (QC-01, QC-03)."""
import json

from survey.models import Question, SurveySection


def _post_form(page, action_url, fields):
    """POST a form via fetch from the browser context, returning status."""
    return page.evaluate(
        """async ({url, fields}) => {
            const fd = new FormData();
            for (const [k, v] of Object.entries(fields)) fd.append(k, v);
            const resp = await fetch(url, {
                method: 'POST',
                body: fd,
                headers: {
                    'X-CSRFToken': document.querySelector(
                        'input[name=csrfmiddlewaretoken]'
                    ).value,
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });
            return resp.status;
        }""",
        {"url": action_url, "fields": fields},
    )


def test_create_text_question_persists(
    logged_in_page, base_url, draft_survey
):
    """
    QC-01.

    GIVEN a draft survey with a head section
    WHEN the user opens the New Question modal and submits with input_type=text
    THEN a Question row is created with the correct section, name and order_number.
    """
    survey = draft_survey
    section = SurveySection.objects.get(survey_header=survey, is_head=True)
    initial_count = Question.objects.filter(survey_section=section).count()

    logged_in_page.goto(f"{base_url}/editor/surveys/{survey.uuid}/")
    logged_in_page.wait_for_selector("#section-form")

    status = _post_form(
        logged_in_page,
        f"/editor/surveys/{survey.uuid}/sections/{section.id}/questions/new/",
        {
            "name": "What's your favorite city?",
            "subtext": "Just one, please",
            "input_type": "text",
            "required": "on",
            "color": "#000000",
            "icon_class": "",
        },
    )
    assert status in (200, 204), f"question create returned {status}"

    questions = Question.objects.filter(survey_section=section)
    assert questions.count() == initial_count + 1, (
        "Question count did not increase after create"
    )
    new_q = questions.order_by("-id").first()
    assert new_q.name == "What's your favorite city?", (
        f"name not persisted; got {new_q.name!r}"
    )
    assert new_q.input_type == "text"
    # Auto-assigned to the next available position in the section.
    assert new_q.order_number == initial_count + 1


def test_choice_question_with_inline_choices(
    logged_in_page, base_url, draft_survey
):
    """
    QC-03.

    GIVEN a draft survey with a head section
    WHEN a choice question is created with three inline choices via choices_json
    THEN ``Question.choices`` stores the JSON list verbatim and translated
        names are accessible via ``get_choice_name``.
    """
    survey = draft_survey
    section = SurveySection.objects.get(survey_header=survey, is_head=True)

    choices = [
        {"code": 1, "name": "Yes"},
        {"code": 2, "name": "No"},
        {"code": 3, "name": "Maybe"},
    ]

    logged_in_page.goto(f"{base_url}/editor/surveys/{survey.uuid}/")
    logged_in_page.wait_for_selector("#section-form")

    status = _post_form(
        logged_in_page,
        f"/editor/surveys/{survey.uuid}/sections/{section.id}/questions/new/",
        {
            "name": "Do you commute by bike?",
            "subtext": "",
            "input_type": "choice",
            "required": "on",
            "color": "#000000",
            "icon_class": "",
            "choices_json": json.dumps(choices),
        },
    )
    assert status in (200, 204), f"choice question create returned {status}"

    new_q = Question.objects.filter(
        survey_section=section, input_type="choice"
    ).order_by("-id").first()
    assert new_q is not None, "choice question was not persisted"
    assert new_q.choices == choices, (
        f"choices not persisted verbatim; got {new_q.choices!r}"
    )
    assert new_q.get_choice_name(1) == "Yes"
    assert new_q.get_choice_name(2) == "No"
    assert new_q.get_choice_name(3) == "Maybe"
