"""End-to-end tests for session validation, clean export and bulk
operations (AV-01, AV-02, BO-01, BO-02, SD-01)."""
import csv
import io
import uuid
import zipfile

import pytest

from survey.models import Answer, Question, SurveySection, SurveySession


@pytest.fixture
def survey_with_three_sessions(test_user):
    from tests_e2e.conftest import _build_survey, _purge_survey

    survey = _build_survey(
        name=f"e2e-validation-{uuid.uuid4().hex[:6]}",
        basemaps=["streets"],
        owner=test_user,
        sections_count=1,
        add_point=False,
    )
    section = SurveySection.objects.get(survey_header=survey, is_head=True)
    text_q = Question.objects.create(
        survey_section=section,
        name="Your name?",
        input_type="text_line",
        order_number=1,
        code="Q_NAME",
        required=False,
    )
    sessions = []
    for label in ["Alice", "Bob", "Carol"]:
        sess = SurveySession.objects.create(survey=survey, language=None)
        Answer.objects.create(survey_session=sess, question=text_q, text=label)
        sessions.append(sess)

    yield survey, text_q, sessions
    _purge_survey(survey)


def _post_json(page, url, body):
    return page.evaluate(
        """async ({url, body}) => {
            const resp = await fetch(url, {
                method: 'POST',
                body: JSON.stringify(body),
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': document.cookie.split('csrftoken=')[1]?.split(';')[0] || '',
                    'HX-Request': 'true'
                }
            });
            return resp.status;
        }""",
        {"url": url, "body": body},
    )


def test_session_validation_status_persists(
    logged_in_page, base_url, survey_with_three_sessions
):
    """
    AV-01.

    GIVEN three sessions on a survey
    WHEN the owner sets one session's status to "approved" and another's
        to "not_approved" via the analytics endpoint
    THEN both validation_status values are persisted in the DB.
    """
    survey, _, sessions = survey_with_three_sessions
    s_yes, s_no, _s_neutral = sessions

    logged_in_page.goto(f"{base_url}/editor/surveys/{survey.uuid}/analytics/")
    logged_in_page.wait_for_load_state("networkidle")

    for sid, target in [(s_yes.id, "approved"), (s_no.id, "not_approved")]:
        url = f"/editor/surveys/{survey.uuid}/analytics/sessions/{sid}/status/"
        status_code = logged_in_page.evaluate(
            """async ({url, target}) => {
                const fd = new FormData();
                fd.append('validation_status', target);
                const resp = await fetch(url, {
                    method: 'POST',
                    body: fd,
                    headers: {
                        'X-CSRFToken': document.cookie
                            .split('csrftoken=')[1]?.split(';')[0] || ''
                    }
                });
                return resp.status;
            }""",
            {"url": url, "target": target},
        )
        assert status_code == 204, f"set status returned {status_code}"

    s_yes.refresh_from_db()
    s_no.refresh_from_db()
    assert s_yes.validation_status == "approved"
    assert s_no.validation_status == "not_approved"


def test_clean_export_excludes_not_approved_sessions(
    logged_in_context, logged_in_page, base_url, survey_with_three_sessions
):
    """
    AV-02.

    GIVEN three sessions where one is marked "not_approved"
    WHEN the owner downloads the survey data
    THEN the default download omits the not-approved session and the
        ``?include_all=1`` flag brings it back.
    """
    survey, _, sessions = survey_with_three_sessions
    s_alice, s_bob, _s_carol = sessions

    s_bob.validation_status = "not_approved"
    s_bob.save(update_fields=["validation_status"])

    api = logged_in_context.request

    clean_zip = api.get(f"{base_url}/surveys/{survey.uuid}/download")
    clean = zipfile.ZipFile(io.BytesIO(clean_zip.body()))
    csv_name = next(n for n in clean.namelist() if n.endswith(".csv"))
    rows = list(csv.DictReader(clean.read(csv_name).decode().splitlines()))
    names = sorted(r.get("Q_NAME") or r.get("Your name?") or "" for r in rows)
    assert names == ["Alice", "Carol"], (
        f"Clean export should drop not_approved Bob; got {names}"
    )

    full_zip = api.get(f"{base_url}/surveys/{survey.uuid}/download?include_all=1")
    full = zipfile.ZipFile(io.BytesIO(full_zip.body()))
    csv_name = next(n for n in full.namelist() if n.endswith(".csv"))
    rows = list(csv.DictReader(full.read(csv_name).decode().splitlines()))
    names = sorted(r.get("Q_NAME") or r.get("Your name?") or "" for r in rows)
    assert names == ["Alice", "Bob", "Carol"], (
        f"include_all should bring Bob back; got {names}"
    )


def test_bulk_set_status_marks_multiple_sessions(
    logged_in_page, base_url, survey_with_three_sessions
):
    """
    BO-01 + BO-02.

    GIVEN three sessions, all with no validation status
    WHEN the owner POSTs the bulk-status endpoint with two session IDs
        and ``status=approved``
    THEN those two sessions have validation_status="approved" and the
        third is left untouched.
    """
    survey, _, sessions = survey_with_three_sessions
    s_a, s_b, s_c = sessions

    logged_in_page.goto(f"{base_url}/editor/surveys/{survey.uuid}/analytics/")
    logged_in_page.wait_for_load_state("networkidle")

    status_code = _post_json(
        logged_in_page,
        f"/editor/surveys/{survey.uuid}/analytics/bulk/status/",
        {"session_ids": [s_a.id, s_b.id], "status": "approved"},
    )
    assert status_code == 204, f"bulk status returned {status_code}"

    s_a.refresh_from_db(); s_b.refresh_from_db(); s_c.refresh_from_db()
    assert s_a.validation_status == "approved"
    assert s_b.validation_status == "approved"
    assert s_c.validation_status == "" or s_c.validation_status is None, (
        f"Third session should be untouched; got {s_c.validation_status!r}"
    )


def test_session_detail_panel_renders_metadata(
    logged_in_page, base_url, survey_with_three_sessions
):
    """
    SD-01.

    GIVEN a recorded session with one text answer
    WHEN the owner opens the session detail endpoint
    THEN the response body includes the answer text.
    """
    survey, _, sessions = survey_with_three_sessions
    s_a = sessions[0]

    logged_in_page.goto(f"{base_url}/editor/surveys/{survey.uuid}/analytics/")
    logged_in_page.wait_for_load_state("networkidle")

    detail_url = f"/editor/surveys/{survey.uuid}/analytics/sessions/{s_a.id}/"
    body = logged_in_page.evaluate(
        """async (url) => {
            const resp = await fetch(url, {
                headers: {'HX-Request': 'true'}
            });
            return await resp.text();
        }""",
        detail_url,
    )
    assert "Alice" in body, f"Session detail should include the recorded answer 'Alice'"
