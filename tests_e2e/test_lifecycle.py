"""End-to-end tests for survey lifecycle transitions (LS-01)."""


def test_lifecycle_transitions_draft_to_archived(
    logged_in_page, base_url, draft_survey
):
    """
    LS-01.

    GIVEN a survey in ``draft`` status
    WHEN the owner sequentially issues transition POSTs to testing,
        published, closed and finally archived
    THEN ``SurveyHeader.status`` reflects each step and the
        ``is_archived`` flag flips when the final transition lands.
    """
    survey = draft_survey

    logged_in_page.goto(f"{base_url}/editor/surveys/{survey.uuid}/")
    logged_in_page.wait_for_load_state("networkidle")

    transition_url = f"/editor/surveys/{survey.uuid}/transition/"

    def transition(status, extra=None):
        body = {"status": status}
        if extra:
            body.update(extra)
        return logged_in_page.evaluate(
            """async ({url, body}) => {
                const fd = new FormData();
                for (const [k, v] of Object.entries(body)) fd.append(k, v);
                const resp = await fetch(url, {
                    method: 'POST',
                    body: fd,
                    headers: {
                        'X-CSRFToken': document.querySelector(
                            'input[name=csrfmiddlewaretoken]'
                        ).value,
                        'HX-Request': 'true'
                    }
                });
                return resp.status;
            }""",
            {"url": transition_url, "body": body},
        )

    assert transition("testing") in (200, 204), "draft → testing failed"
    survey.refresh_from_db()
    assert survey.status == "testing"

    assert transition("published", {"clear_test_data": "true"}) in (200, 204), (
        "testing → published failed"
    )
    survey.refresh_from_db()
    assert survey.status == "published"

    assert transition("closed") in (200, 204), "published → closed failed"
    survey.refresh_from_db()
    assert survey.status == "closed"

    assert transition("archived") in (200, 204), "closed → archived failed"
    survey.refresh_from_db()
    assert survey.status == "archived"
    assert survey.is_archived is True, "archived transition did not set is_archived"
