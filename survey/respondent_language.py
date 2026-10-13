"""The survey's language on every respondent page, not only its sections.

The section views activate `session['survey_language']`; the thanks, password,
closed, unavailable and report pages used to render in whatever LocaleMiddleware
resolved from the browser, so a respondent with an English browser finished a
Polish survey on an English page.
"""
from django.utils import translation


def survey_language(request, survey):
    """The language this respondent should see `survey` in, or None.

    In order: the language picked for a survey in this session, if this survey
    offers it (or names no languages at all); the browser's language, if offered; the survey's first language.
    `session['survey_language']` is one site-wide value, so a pick made for
    another survey only counts when this survey offers it too.
    """
    offered = list(survey.available_languages or [])
    picked = request.session.get('survey_language')
    if not offered:
        # Older surveys name no languages; the section view still honours the
        # session's pick for them, so the pages around it do too.
        return picked
    if picked in offered:
        return picked
    browser = translation.get_language_from_request(request)
    if browser in offered:
        return browser
    if browser and browser.split('-')[0] in offered:
        return browser.split('-')[0]
    return offered[0]


def activate_survey_language(request, survey):
    """Activate the survey's language for the rest of this request.

    Only `translation.activate()` -- never the language cookie -- so a creator
    who also takes a survey keeps their own editor language.
    """
    lang = survey_language(request, survey)
    if lang:
        translation.activate(lang)
    return lang
