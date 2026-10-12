"""Where a respondent goes after the last section (change fix-redirect-url-validation, #271).

`SurveyHeader.redirect_url` is either "#" -- the built-in thanks page -- or an
absolute http(s) URL. It used to be free text, and creators wrote hashtags,
thank-you messages and "#https://..." (the box was pre-filled with "#") into it;
the final-section redirect then went to "#tag" and left respondents pressing
Finish on the same page. Every reader goes through `completion_url()`, so a value
that is not a real URL can never trap anyone, whatever is stored.
"""
import re

from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.urls import reverse

NO_REDIRECT = '#'

_url_validator = URLValidator(schemes=['http', 'https'])
_LEADING_ANCHOR_BEFORE_URL = re.compile(r'^#+(?=https?://)', re.IGNORECASE)
_SCHEME = re.compile(r'^(https?)://', re.IGNORECASE)


def tidy_redirect_input(value):
    """The fixes a creator would make by hand: drop the "#" typed in front of a
    URL, give a bare "www." address a scheme, lowercase the scheme. Validates
    nothing -- see `is_valid_redirect`."""
    value = (value or '').strip()
    value = _LEADING_ANCHOR_BEFORE_URL.sub('', value)
    if value.lower().startswith('www.'):
        value = 'https://' + value
    return _SCHEME.sub(lambda m: m.group(1).lower() + '://', value)


def is_valid_redirect(value):
    # 250 = SurveyHeader.redirect_url max_length; tidying can add "https://".
    if len(value) > 250:
        return False
    try:
        _url_validator(value)
    except ValidationError:
        return False
    return True


def clean_redirect_url(value):
    """"#" or a valid absolute http(s) URL. Never raises."""
    value = tidy_redirect_input(value)
    return value if is_valid_redirect(value) else NO_REDIRECT


def completion_url(survey):
    """The URL a respondent is sent to after the survey's last section."""
    target = clean_redirect_url(survey.redirect_url)
    if target == NO_REDIRECT:
        return reverse('survey_thanks', args=[str(survey.uuid)])
    return target
