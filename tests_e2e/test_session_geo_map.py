"""End-to-end tests for viewing one response's geo objects on a map.

These live here rather than in survey/tests.py on purpose: every defect this
change fixed was invisible to the Django test client. The dead mini-map was a
JavaScript handler bound to a node that no longer existed, and the drawer's
missing scrollbar was a CSS height rule — a rendered-markup assertion passes in
both cases. Only a real browser sees them.
"""
import uuid

import pytest
from django.contrib.gis.geos import LineString, Point

from survey.models import Answer, Question, SurveySection, SurveySession


@pytest.fixture
def survey_with_geo_responses(test_user):
    """A published survey holding one response with several geo objects."""
    from tests_e2e.conftest import _build_survey, _purge_survey

    survey = _build_survey(
        name=f"e2e-session-geo-{uuid.uuid4().hex[:6]}",
        basemaps=["streets"],
        owner=test_user,
        sections_count=1,
        add_point=False,
    )
    section = SurveySection.objects.get(survey_header=survey, is_head=True)
    point_q = Question.objects.create(
        survey_section=section, name="Mark a place you love",
        input_type="point", order_number=1, code="Q_PT", required=False,
    )
    line_q = Question.objects.create(
        survey_section=section, name="Draw your commute",
        input_type="line", order_number=2, code="Q_LN", required=False,
    )

    session = SurveySession.objects.create(survey=survey, language=None)
    # Two objects for one question: the numbered labels must tell them apart.
    Answer.objects.create(survey_session=session, question=point_q, point=Point(13.40, 52.52))
    Answer.objects.create(survey_session=session, question=point_q, point=Point(13.42, 52.53))
    Answer.objects.create(
        survey_session=session, question=line_q,
        line=LineString((13.40, 52.52), (13.44, 52.55)),
    )
    # A few plain responses so the table has rows and a pager.
    for _ in range(3):
        SurveySession.objects.create(survey=survey, language=None)

    yield survey, session
    _purge_survey(survey)


def _open_drawer(page, base_url, survey, session):
    page.goto(f"{base_url}/editor/surveys/{survey.uuid}/analytics/#responses")
    page.wait_for_load_state("networkidle")
    # The debug toolbar overlays the page in DEBUG and swallows clicks.
    page.evaluate("const d = document.getElementById('djDebug'); if (d) d.remove();")
    page.evaluate(f"rv2OpenSession({session.id})")
    page.wait_for_selector("#session-mini-map", timeout=10000)
    page.wait_for_timeout(2000)


def test_drawer_geo_preview_renders_a_map(
    logged_in_page, base_url, survey_with_geo_responses
):
    """
    GIVEN a response holding geo objects
    WHEN the creator opens it in the detail drawer
    THEN the preview contains an initialised Leaflet map, not an empty box
    """
    survey, session = survey_with_geo_responses
    _open_drawer(logged_in_page, base_url, survey, session)

    initialised = logged_in_page.evaluate(
        "!!document.querySelector('#session-mini-map .leaflet-container,"
        " #session-mini-map .leaflet-pane')"
    )
    assert initialised, (
        "the drawer preview rendered no Leaflet map — the initialiser is bound "
        "to a node this surface does not have"
    )


def test_geo_rows_read_as_values_not_type_names(
    logged_in_page, base_url, survey_with_geo_responses
):
    """
    GIVEN a response with a point and a line answer
    WHEN the detail drawer renders their rows
    THEN each row shows coordinates or a vertex count, and offers a map control
    """
    survey, session = survey_with_geo_responses
    _open_drawer(logged_in_page, base_url, survey, session)

    values = logged_in_page.evaluate(
        "[...document.querySelectorAll('#rv2-drawer-body .session-geo-open')]"
        ".map(b => b.closest('td').querySelector('span').innerText.trim())"
    )
    assert len(values) == 3, f"expected a map control per geo object, got {values}"
    assert any("," in v for v in values), f"no coordinates among {values}"
    assert any("vertices" in v for v in values), f"no vertex count among {values}"
    assert not any(v.endswith("feature") for v in values), (
        f"rows still show the bare type name: {values}"
    )


def test_full_size_map_opens_from_both_entry_points(
    logged_in_page, base_url, survey_with_geo_responses
):
    """
    GIVEN a response open in the detail drawer
    WHEN the creator activates the preview, and then a single geo row
    THEN the full-size map opens in both cases, with a legend, the response's
         objects, and — from the row — that object's popup
    """
    survey, session = survey_with_geo_responses
    _open_drawer(logged_in_page, base_url, survey, session)

    logged_in_page.click("#session-mini-map")
    logged_in_page.wait_for_timeout(2500)
    state = logged_in_page.evaluate(
        """() => {
            const m = document.getElementById('session-geo-modal-map');
            return {
                shown: document.getElementById('sessionGeoMapModal').classList.contains('show'),
                leaflet: !!m.querySelector('.leaflet-container, .leaflet-pane'),
                height: Math.round(m.getBoundingClientRect().height),
                legendRows: document.getElementById('session-geo-modal-legend').children.length,
            };
        }"""
    )
    assert state["shown"] and state["leaflet"], state
    assert state["height"] > 100, f"map opened with no height: {state}"
    # Two geo questions in this survey → two legend entries.
    assert state["legendRows"] == 2, state

    logged_in_page.evaluate("$('#sessionGeoMapModal').modal('hide')")
    logged_in_page.wait_for_timeout(1200)

    logged_in_page.click(".session-geo-open")
    logged_in_page.wait_for_timeout(2500)
    popup = logged_in_page.evaluate(
        "(document.querySelector('.leaflet-popup-content') || {}).innerText || ''"
    )
    assert "Mark a place you love" in popup, (
        f"opening from a row did not surface that object: {popup!r}"
    )


def test_reopening_the_map_leaves_no_stale_instance(
    logged_in_page, base_url, survey_with_geo_responses
):
    """
    GIVEN the full-size map has been opened and closed repeatedly
    WHEN its container is inspected
    THEN exactly one Leaflet instance is attached, not one per opening
    """
    survey, session = survey_with_geo_responses
    _open_drawer(logged_in_page, base_url, survey, session)

    for _ in range(3):
        logged_in_page.click("#session-mini-map")
        logged_in_page.wait_for_timeout(1500)
        logged_in_page.evaluate("$('#sessionGeoMapModal').modal('hide')")
        logged_in_page.wait_for_timeout(1000)

    containers = logged_in_page.evaluate(
        "document.querySelectorAll('#session-geo-modal-map .leaflet-container').length"
    )
    assert containers <= 1, f"{containers} Leaflet instances left attached"


def test_drawer_scrolls_itself_and_pagination_stays_on_screen(
    logged_in_page, base_url, survey_with_geo_responses
):
    """
    GIVEN the detail drawer is open on a desktop viewport
    WHEN the workspace is measured
    THEN the drawer scrolls inside itself and the table's pagination is visible

    Regression guard: `.rv2` used min-height, so the workspace grew with its
    content. Every `flex: 1; min-height: 0` below it then constrained nothing —
    the drawer scrolled with the page and the pager was pushed off screen.
    """
    survey, session = survey_with_geo_responses
    logged_in_page.set_viewport_size({"width": 1600, "height": 800})
    _open_drawer(logged_in_page, base_url, survey, session)

    measured = logged_in_page.evaluate(
        """() => {
            /* The page-number text only renders past one page of rows; the
               footer itself (Rows selector, Prev/Next) is always there and is
               what gets pushed off screen. */
            const pager = document.querySelector('.attr-pagination');
            const r = pager ? pager.getBoundingClientRect() : null;
            const body = document.getElementById('rv2-drawer-body');
            return {
                pagerFound: !!pager,
                pagerVisible: !!(r && r.bottom <= window.innerHeight + 1 && r.top >= 0),
                pageScrolls: document.documentElement.scrollHeight > window.innerHeight + 2,
                drawerOverflows: body.scrollHeight > body.clientHeight + 2,
            };
        }"""
    )
    assert measured["pagerFound"], "no table footer on the page"
    assert measured["pagerVisible"], f"the table footer is off screen: {measured}"
    assert not measured["pageScrolls"], f"the whole page scrolls: {measured}"
    assert measured["drawerOverflows"], (
        f"drawer content did not overflow, so its own scrolling is untested: {measured}"
    )
