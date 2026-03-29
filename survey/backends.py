from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend

UserModel = get_user_model()


class EmailOrUsernameBackend(ModelBackend):
    """Authenticate by username or email address."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None or password is None:
            return None

        # Try username first (default behavior)
        try:
            user = UserModel.objects.get(username=username)
        except UserModel.DoesNotExist:
            # Try email lookup
            try:
                user = UserModel.objects.get(email__iexact=username)
            except (UserModel.DoesNotExist, UserModel.MultipleObjectsReturned):
                return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
