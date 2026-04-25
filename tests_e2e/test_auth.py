"""End-to-end tests for authentication and registration (AU-01 .. AU-04)."""
import uuid

import pytest
from django.contrib.auth.models import User

from survey.models import Membership, Organization


@pytest.fixture
def disposable_username():
    name = f"e2e_reg_{uuid.uuid4().hex[:8]}"
    yield name
    user = User.objects.filter(username=name).first()
    if user:
        for m in user.memberships.all():
            org = m.organization
            m.delete()
            if not org.memberships.exists():
                org.delete()
        user.delete()


def _fill_register_form(page, *, username, email, password):
    page.fill('input[name="username"]', username)
    page.fill('input[name="email"]', email)
    page.fill('input[name="password1"]', password)
    page.fill('input[name="password2"]', password)
    page.click('button[type="submit"], input[type="submit"]')


def test_register_creates_user_and_personal_org(page, base_url, disposable_username):
    """
    AU-01.

    GIVEN a fresh username and email
    WHEN the registration form is submitted with a strong password
    THEN a User record is created (inactive, awaiting activation) and a
        personal Organization with an owner Membership is created via the
        ``user_registered`` signal.
    """
    page.goto(f"{base_url}/accounts/register/")
    _fill_register_form(
        page,
        username=disposable_username,
        email=f"{disposable_username}@test.local",
        password="ZxqA12345!",
    )
    page.wait_for_load_state("networkidle")

    user = User.objects.filter(username=disposable_username).first()
    assert user is not None, "User row was not created on registration"
    assert user.is_active is False, "Activation email flow expected user.is_active=False"

    membership = Membership.objects.filter(user=user, role="owner").first()
    assert membership is not None, "Owner Membership not created by user_registered signal"
    assert membership.organization.name.startswith(disposable_username), (
        "Personal organization not named after the user"
    )


def test_register_duplicate_username_shows_error(
    page, base_url, test_user, disposable_username
):
    """
    AU-02.

    GIVEN a username already taken by ``test_user``
    WHEN the registration form is submitted with the same username
    THEN the page does not redirect to the activation-pending screen and
        an inline form error is rendered.
    """
    # disposable_username is unused here — we want a guaranteed-clash username
    del disposable_username

    page.goto(f"{base_url}/accounts/register/")
    _fill_register_form(
        page,
        username=test_user.username,
        email="another@test.local",
        password="ZxqA12345!",
    )
    page.wait_for_load_state("networkidle")

    # We should still be on the register page (form re-rendered with errors)
    assert "/accounts/register/" in page.url, (
        f"Expected to stay on register page, got {page.url}"
    )
    body = page.locator("body").inner_text().lower()
    assert "already" in body or "exist" in body or "taken" in body, (
        "Expected an error mentioning the username clash"
    )


def test_login_with_valid_credentials_redirects_to_editor(page, base_url, test_user):
    """
    AU-03.

    GIVEN the seeded ``e2e_tester`` account is active
    WHEN valid credentials are submitted on /accounts/login/
    THEN the browser lands on /editor/.
    """
    page.goto(f"{base_url}/accounts/login/")
    page.fill('input[name="username"]', test_user.username)
    page.fill('input[name="password"]', "TestPass123!")
    page.click('button[type="submit"]')
    page.wait_for_url(f"{base_url}/editor/")

    assert page.url.rstrip("/") == f"{base_url}/editor", (
        f"Expected redirect to /editor/, landed on {page.url}"
    )


def test_login_with_wrong_password_shows_error(page, base_url, test_user):
    """
    AU-04.

    GIVEN the seeded ``e2e_tester`` account is active
    WHEN an obviously wrong password is submitted
    THEN the page stays on /accounts/login/ and an error message is rendered.
    """
    page.goto(f"{base_url}/accounts/login/")
    page.fill('input[name="username"]', test_user.username)
    page.fill('input[name="password"]', "definitely-wrong")
    page.click('button[type="submit"]')
    page.wait_for_load_state("networkidle")

    assert "/accounts/login/" in page.url, (
        f"Expected to stay on login page, got {page.url}"
    )
    body = page.locator("body").inner_text().lower()
    assert "correct" in body or "invalid" in body or "incorrect" in body or "match" in body, (
        "Expected a generic auth error message after a wrong password"
    )
