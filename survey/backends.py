from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend

UserModel = get_user_model()


def find_user(identifier):
    """The account an identifier names: username first, then email (case-insensitive).

    Shared with `survey.auth_forms.SignInForm`, which looks the account up again
    to tell a correct password on an unconfirmed account from a wrong one; the
    two lookups must never disagree.
    """
    try:
        return UserModel.objects.get(username=identifier)
    except UserModel.DoesNotExist:
        try:
            return UserModel.objects.get(email__iexact=identifier)
        except (UserModel.DoesNotExist, UserModel.MultipleObjectsReturned):
            return None


class EmailOrUsernameBackend(ModelBackend):
    """Authenticate by username or email address.

    Sign-in follows `email_verification.can_sign_in`: not banned, and a
    confirmed address or still inside the grace period (change
    login-grace-period). Restoring a session (`get_user`) checks only the ban;
    `GracePeriodMiddleware` ends a session at the deadline and says why, which a
    silently anonymous request could not.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None or password is None:
            return None
        user = find_user(username)
        if user is None:
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None

    def user_can_authenticate(self, user):
        from .email_verification import can_sign_in
        return can_sign_in(user)

    def get_user(self, user_id):
        try:
            user = UserModel._default_manager.get(pk=user_id)
        except UserModel.DoesNotExist:
            return None
        return user if user.is_active else None
