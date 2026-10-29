"""The sign-in form and view (change login-grace-period, #487).

The one place sign-in may say more than "invalid username or password": a
correct password for an account whose address is still unconfirmed after the
grace period. The visitor has just proven they hold the account, so naming the
reason reveals nothing; and they get a fresh link in the same request. Every
other failure — wrong password, unknown identifier, banned account — keeps the
generic message, so the form still does not enumerate accounts.
"""

from django import forms
from django.conf import settings
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.views import LoginView
from django.utils.translation import gettext_lazy as _

from .backends import find_user
from .email_verification import awaits_confirmation, mask_email, send_link


class SignInForm(AuthenticationForm):
    error_messages = {
        **AuthenticationForm.error_messages,
        'email_unconfirmed': _('Your email address was not confirmed in time.'),
    }

    # Set when the email_unconfirmed error is raised: see `unconfirmed_notice`.
    unconfirmed = None

    def clean(self):
        try:
            return super().clean()
        except forms.ValidationError as error:
            if getattr(error, 'code', None) != 'invalid_login':
                raise
            info = self._unconfirmed_case()
            if info is None:
                raise
            self.unconfirmed = info
            raise forms.ValidationError(
                self.error_messages['email_unconfirmed'], code='email_unconfirmed',
            ) from None

    def _unconfirmed_case(self):
        user = find_user(self.cleaned_data.get('username') or '')
        if user is None or not awaits_confirmation(user):
            return None
        if not user.check_password(self.cleaned_data.get('password') or ''):
            return None
        return unconfirmed_notice(user, send_link(user, self.request, source='sign_in'))


def unconfirmed_notice(user, sent):
    """What the sign-in page shows: the masked address, whether a mail just
    went out, and the grace period it was not confirmed within."""
    return {
        'masked': mask_email(user.email),
        'sent': bool(sent),
        'hours': settings.SIGN_IN_GRACE_HOURS,
    }


# Session key `GracePeriodMiddleware` leaves for the sign-in page after it ends
# a session at the deadline.
SESSION_NOTICE_KEY = 'ms_unconfirmed_notice'


class SignInView(LoginView):
    authentication_form = SignInForm

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        form = ctx.get('form')
        notice = getattr(form, 'unconfirmed', None)
        if notice is None and self.request.method == 'GET':
            notice = self.request.session.pop(SESSION_NOTICE_KEY, None)
        ctx['unconfirmed'] = notice
        return ctx
