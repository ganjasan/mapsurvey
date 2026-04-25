"""Shared fixtures for Playwright end-to-end tests against a running dev server.

Pre-conditions before running:
- Dev server is up on http://localhost:8000 (e.g. via ``./run_dev.sh``)
- PostGIS container is running on port 5434
- The Django venv is active so the ORM can be imported

Run with:
- ``pytest tests_e2e/`` — headless, fast (default)
- ``./run_e2e.sh --visible`` — opens a real Chromium window
- ``./run_e2e.sh --visible --slow`` — same, slowed to 500 ms/action
- ``./run_e2e.sh --debug`` — opens Playwright Inspector for step-by-step debugging

Any pytest-playwright flag works directly too:
- ``pytest tests_e2e/ --headed --slowmo=500``
- ``pytest tests_e2e/ -k satellite --headed``
"""
import os
import time
import uuid

import django
import pytest

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mapsurvey.settings")
os.environ.setdefault("SQL_HOST", "localhost")
os.environ.setdefault("SQL_PORT", "5434")
# pytest-playwright runs the suite inside an asyncio event loop. Tell Django
# it is OK to issue ORM calls from this context — we are not actually mixing
# async and sync ORM in user code, only running fixtures via pytest.
os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")
django.setup()

from django.contrib.auth.models import User  # noqa: E402
from django.utils.text import slugify  # noqa: E402

from survey.models import (  # noqa: E402
    Membership,
    Organization,
    Question,
    SurveyHeader,
    SurveySection,
    SurveySession,
)


def _purge_survey(survey):
    """Delete a survey along with any sessions created during the test.

    The live dev server may create a SurveySession concurrently with teardown
    (browser still draining requests), so we retry the delete a few times,
    refetching the survey by UUID before each attempt.
    """
    from django.db import IntegrityError, transaction

    survey_uuid = survey.uuid
    for _ in range(5):
        try:
            current = SurveyHeader.objects.filter(uuid=survey_uuid).first()
            if current is None:
                return
            with transaction.atomic():
                SurveySession.objects.filter(survey=current).delete()
                current.delete()
            return
        except IntegrityError:
            time.sleep(0.3)
    # Last-ditch: rename the leaked survey so it's easy to spot in the dashboard
    leaked = SurveyHeader.objects.filter(uuid=survey_uuid).first()
    if leaked:
        leaked.name = f"__leaked_{leaked.name}"[:200]
        leaked.save(update_fields=["name"])

BASE_URL = os.environ.get("E2E_BASE_URL", "http://localhost:8000")
TEST_USERNAME = "e2e_tester"
TEST_PASSWORD = "TestPass123!"


@pytest.fixture(scope="session")
def django_db_setup(django_db_blocker):
    """Disable pytest-django test DB creation — these tests share the dev DB.

    Also unblocks DB access for the entire session so ORM fixtures can run
    without each test having to declare a ``django_db`` mark.
    """
    django_db_blocker.unblock()
    yield


@pytest.fixture(autouse=True)
def _ensure_db_unblocked(django_db_blocker):
    """Function-scoped DB unblock for individual tests."""
    with django_db_blocker.unblock():
        yield


@pytest.fixture(scope="session")
def base_url():
    return BASE_URL


@pytest.fixture(scope="session")
def test_user(django_db_setup):
    user, _ = User.objects.get_or_create(
        username=TEST_USERNAME,
        defaults={"email": "e2e@test.local", "is_active": True},
    )
    user.set_password(TEST_PASSWORD)
    user.is_active = True
    user.save()
    if not user.memberships.exists():
        slug = slugify(f"{user.username}-workspace")[:100] or "workspace"
        org, _ = Organization.objects.get_or_create(
            slug=slug,
            defaults={"name": f"{user.username}'s workspace"},
        )
        Membership.objects.get_or_create(
            user=user, organization=org, defaults={"role": "owner"}
        )
    return user


@pytest.fixture
def logged_in_context(browser, base_url, test_user):
    """Yield a Playwright context with an active session cookie."""
    context = browser.new_context()
    page = context.new_page()
    page.goto(f"{base_url}/accounts/login/")
    page.fill('input[name="username"]', TEST_USERNAME)
    page.fill('input[name="password"]', TEST_PASSWORD)
    page.click('button[type="submit"]')
    page.wait_for_url(f"{base_url}/editor/")
    yield context
    context.close()


@pytest.fixture
def logged_in_page(logged_in_context):
    page = logged_in_context.new_page()
    yield page
    page.close()


def _build_survey(*, name: str, basemaps, owner, status="published",
                  add_range=False, add_point=True, sections_count=2):
    """Create a survey owned by ``owner`` with the given basemaps and content."""
    org = owner.memberships.first().organization
    survey = SurveyHeader.objects.create(
        name=name,
        organization=org,
        created_by=owner,
        status=status,
        basemaps=basemaps,
        is_canonical=True,
        version_number=1,
    )
    sections = []
    for i in range(1, sections_count + 1):
        section = SurveySection.objects.create(
            survey_header=survey,
            name=f"section_{i}",
            title=f"Section {i}",
            code=f"S{i}",
            is_head=(i == 1),
        )
        sections.append(section)
    # Wire next/prev section pointers
    for i, section in enumerate(sections):
        if i + 1 < len(sections):
            section.next_section = sections[i + 1]
            section.save(update_fields=["next_section"])
        if i > 0:
            section.prev_section = sections[i - 1]
            section.save(update_fields=["prev_section"])

    if add_point:
        Question.objects.create(
            survey_section=sections[0],
            name="Where do you live?",
            input_type="point",
            order_number=1,
        )
    if add_range:
        Question.objects.create(
            survey_section=sections[-1],
            name="How would you rate accessibility?",
            input_type="range",
            order_number=1,
            choices=[
                {"code": 1, "name": "Very poor"},
                {"code": 2, "name": ""},
                {"code": 3, "name": ""},
                {"code": 4, "name": ""},
                {"code": 5, "name": "Excellent"},
            ],
        )
    return survey


@pytest.fixture
def survey_with_all_basemaps(test_user):
    survey = _build_survey(
        name=f"e2e-basemaps-{uuid.uuid4().hex[:8]}",
        basemaps=["streets", "satellite", "topo"],
        owner=test_user,
    )
    yield survey
    _purge_survey(survey)


@pytest.fixture
def survey_with_range_question(test_user):
    survey = _build_survey(
        name=f"e2e-range-{uuid.uuid4().hex[:8]}",
        basemaps=["streets"],
        owner=test_user,
        add_point=False,
        add_range=True,
        sections_count=1,
    )
    yield survey
    _purge_survey(survey)


@pytest.fixture
def draft_survey(test_user):
    survey = _build_survey(
        name=f"e2e-draft-{uuid.uuid4().hex[:8]}",
        basemaps=["streets", "satellite"],
        owner=test_user,
        status="draft",
    )
    yield survey
    _purge_survey(survey)
