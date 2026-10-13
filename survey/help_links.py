"""Links from the product into the help centre (openspec: help-site, #298).

One registry, so a page on help.mapsurvey.org can be renamed without leaving a dead
link behind: `HelpLinksTest` asserts that every path here exists as a page under
`help/src/content/docs/`, and templates build help URLs only through `HELP_URL`
(the `help_site` context processor), never by hand.

Paths are relative to `settings.HELP_SITE_URL` and end with a slash, matching the
site's `trailingSlash: 'always'`. An empty `HELP_SITE_URL` (a self-hosted instance
without a mirror) turns every link off: `HELP_URL` is then empty and templates
render nothing.
"""
from django.conf import settings

HELP_LINKS = {
    'help_home': '',
    'start_here': 'start-here/',
    'reference_layers': 'how-to/add-a-reference-layer/',
    'embedding': 'how-to/embed-a-survey/',
    'export': 'how-to/export-responses/',
    'pro': 'reference/plans-and-billing/',
    'faq': 'faq/',
}


def help_site_url():
    return (getattr(settings, 'HELP_SITE_URL', '') or '').rstrip('/')


def help_urls():
    """{key: absolute URL} for every registry entry, or {} when the help site is off."""
    base = help_site_url()
    if not base:
        return {}
    return {key: f'{base}/{path}' for key, path in HELP_LINKS.items()}
