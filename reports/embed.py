"""Embedding a report, or one of its blocks, on another site (change reports-embed, #708).

The survey embed mechanism, reused: the view marks the response with the ancestors that may frame
it (`request.survey_frame_ancestors`, applied by `SurveyEmbedMiddleware` as `frame-ancestors` in
place of `X-Frame-Options`), the framed page posts `{mapsurvey: "height"}` messages and `/embed.js`
on the host page grows the iframe. A report has its own allow-list (`Report.embed_allowed_hosts`,
empty = any site). Only a report anyone can open is framed: a workspace-only report keeps
`SAMEORIGIN`, and an unpublished one is a 404 to begin with.
"""
from django.urls import reverse
from django.utils.html import escape

REPORT_HEIGHT = 720
BLOCK_HEIGHT = 420


def embeddable(report):
    return report.is_published and report.visibility in ('public', 'unlisted')


def mark(request, report):
    """Let the report's allowed hosts frame this response."""
    from survey.embedding import frame_ancestors
    if embeddable(report):
        request.survey_frame_ancestors = frame_ancestors(report.embed_allowed_hosts or [])


def path(report, block_id=None):
    if block_id:
        return reverse('report_block', args=[report.slug, block_id])
    return reverse('public_results', args=[report.slug])


def snippet(base, report, block_id=None, title='', with_script=True):
    """The iframe an author pastes: the whole report, or one block of it."""
    base = base.rstrip('/')
    height = BLOCK_HEIGHT if block_id else REPORT_HEIGHT
    iframe = ('<iframe src="%s?embed=1" title="%s" height="%d" '
              'style="width:100%%;max-width:100%%;height:%dpx;border:0;" loading="lazy"></iframe>'
              % (escape(base + path(report, block_id)), escape(title or report.title), height, height))
    if not with_script:
        return iframe
    return iframe + '\n<script async src="%s"></script>' % escape(base + reverse('embed_js'))


def clean_hosts(text):
    """The allow-list from the settings field (one host per line or comma-separated). Raises
    `survey.embedding.InvalidHost` naming the entry that is not a host."""
    from survey.embedding import normalise_allowed_hosts
    return normalise_allowed_hosts(text or '')
