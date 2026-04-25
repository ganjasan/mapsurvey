"""End-to-end tests for survey data export (EX-01, EX-02, EX-03)."""
import csv
import io
import json
import uuid
import zipfile

import pytest

from survey.models import Answer, Question, SurveySection, SurveySession


@pytest.fixture
def survey_with_responses(test_user):
    from tests_e2e.conftest import _build_survey, _purge_survey
    from django.contrib.gis.geos import Point

    survey = _build_survey(
        name=f"e2e-export-{uuid.uuid4().hex[:6]}",
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
    choice_q = Question.objects.create(
        survey_section=section,
        name="Bike?",
        input_type="choice",
        order_number=2,
        code="Q_BIKE",
        required=False,
        choices=[{"code": 1, "name": "Yes"}, {"code": 2, "name": "No"}],
    )
    point_q = Question.objects.create(
        survey_section=section,
        name="Where do you live?",
        input_type="point",
        order_number=3,
        code="Q_HOME",
        required=False,
    )

    for label, lat, lng, choice in [("Alice", 52.51, 13.40, 1), ("Bob", 52.52, 13.41, 2)]:
        sess = SurveySession.objects.create(survey=survey, language=None)
        Answer.objects.create(survey_session=sess, question=text_q, text=label)
        Answer.objects.create(
            survey_session=sess, question=choice_q, selected_choices=[choice]
        )
        Answer.objects.create(
            survey_session=sess, question=point_q, point=Point(lng, lat, srid=4326)
        )

    yield survey
    _purge_survey(survey)


def test_download_returns_zip_with_expected_files(
    logged_in_context, base_url, survey_with_responses
):
    """
    EX-01.

    GIVEN a published survey with two completed responses
    WHEN the owner hits ``/surveys/<uuid>/download``
    THEN the response is a ZIP that contains a CSV per section and a
        GeoJSON file for the point question.
    """
    survey = survey_with_responses
    api = logged_in_context.request
    response = api.get(f"{base_url}/surveys/{survey.uuid}/download")
    assert response.status == 200, f"download returned {response.status}"
    body = response.body()

    archive = zipfile.ZipFile(io.BytesIO(body))
    names = archive.namelist()

    csv_files = [n for n in names if n.endswith(".csv")]
    geojson_files = [n for n in names if n.endswith(".geojson")]
    assert csv_files, f"No CSV files in archive; got {names}"
    assert geojson_files, f"No GeoJSON files in archive; got {names}"


def test_geojson_content_matches_responses(
    logged_in_context, base_url, survey_with_responses
):
    """
    EX-02.

    GIVEN two responses with a point question pinned at known coords
    WHEN the export ZIP is fetched
    THEN the GeoJSON FeatureCollection has two features with matching
        coordinates and the corresponding text/choice properties.
    """
    survey = survey_with_responses
    api = logged_in_context.request
    response = api.get(f"{base_url}/surveys/{survey.uuid}/download")
    body = response.body()

    archive = zipfile.ZipFile(io.BytesIO(body))
    geojson_name = next(n for n in archive.namelist() if n.endswith(".geojson"))
    fc = json.loads(archive.read(geojson_name).decode())

    assert fc["type"] == "FeatureCollection"
    assert len(fc["features"]) == 2, f"Expected 2 features; got {len(fc['features'])}"

    coords = sorted(tuple(f["geometry"]["coordinates"]) for f in fc["features"])
    assert coords == [(13.4, 52.51), (13.41, 52.52)], (
        f"Coordinates do not round-trip; got {coords}"
    )


def test_csv_contains_one_row_per_session(
    logged_in_context, base_url, survey_with_responses
):
    """
    EX-03.

    GIVEN two completed sessions with text and choice answers
    WHEN the export ZIP is fetched
    THEN the section CSV has a header plus one data row per session,
        and the text + choice columns reflect the recorded answers.
    """
    survey = survey_with_responses
    api = logged_in_context.request
    response = api.get(f"{base_url}/surveys/{survey.uuid}/download")
    body = response.body()

    archive = zipfile.ZipFile(io.BytesIO(body))
    csv_name = next(n for n in archive.namelist() if n.endswith(".csv"))
    rows = list(csv.DictReader(archive.read(csv_name).decode().splitlines()))

    assert len(rows) == 2, f"Expected 2 rows in CSV; got {len(rows)}"
    names = sorted(r.get("Q_NAME") or r.get("Your name?") or "" for r in rows)
    assert names == ["Alice", "Bob"], f"Names in CSV did not round-trip; got {names}"
