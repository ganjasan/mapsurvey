"""Allow-list sanitizer for creator-authored WYSIWYG HTML.

Two surfaces let a creator write formatted HTML that respondents are then shown
`|safe`: the thanks page (`SurveyHeader.thanks_html`) and the Formatted Text block
(`Question.subtext` where `input_type == 'html'`). Both go through here on save,
so neither can become a stored-XSS vector.

It lives in its own module rather than in `views.py` because `editor_forms` needs
it too, and importing a view module from a form module would close an import loop.
"""

import re
from urllib.parse import urlparse

from django.utils.html import escape

# The tags a creator may produce from the Quill toolbars we expose.
CREATOR_HTML_ALLOWED_TAGS = {
	'h1', 'h2', 'h3', 'h4', 'p', 'br', 'strong', 'b', 'em', 'i', 'u', 's',
	'a', 'ul', 'ol', 'li', 'blockquote', 'span', 'div', 'img', 'iframe',
}
_STYLE_TAGS = {'p', 'h1', 'h2', 'h3', 'h4', 'div', 'blockquote', 'li', 'span'}
CREATOR_HTML_ALLOWED_ATTRS = {
	'a': {'href', 'title', 'target'},  # rel is managed by link_rel
	'img': {'src', 'alt', 'width', 'height'},
	'iframe': {'src', 'width', 'height', 'frameborder', 'allowfullscreen', 'allow'},
}
# Allow a `style` attribute (restricted to text-align via filter_style_properties)
# on text/block tags so alignment survives on the public page.
for _t in _STYLE_TAGS:
	CREATOR_HTML_ALLOWED_ATTRS[_t] = {'style'}
# Only these hosts may be embedded as <iframe> video (Quill video button).
CREATOR_VIDEO_HOSTS = {
	'www.youtube.com', 'youtube.com', 'www.youtube-nocookie.com',
	'youtube-nocookie.com', 'player.vimeo.com', 'vimeo.com',
}


def _creator_attr_filter(tag, attr, value):
	"""nh3 per-attribute filter: restrict <iframe> src to trusted video hosts.
	Return None to drop the attribute."""
	if tag == 'iframe' and attr == 'src':
		try:
			host = (urlparse(value).hostname or '').lower()
		except ValueError:
			return None
		return value if host in CREATOR_VIDEO_HOSTS else None
	return value


def sanitize_creator_html(html):
	"""Sanitize creator WYSIWYG HTML against the allow-list.

	Strips scripts, event handlers, and unknown tags/attributes; keeps basic
	formatting, alignment (inline text-align only), images, and trusted-host
	video iframes; forces safe rel on links. Returns '' for falsy input.
	"""
	if not html:
		return ''
	import nh3
	return nh3.clean(
		str(html),
		tags=CREATOR_HTML_ALLOWED_TAGS,
		attributes=CREATOR_HTML_ALLOWED_ATTRS,
		attribute_filter=_creator_attr_filter,
		filter_style_properties={'text-align'},
		url_relative='pass_through',
		link_rel='noopener noreferrer',
	)


# A creator's own markup always opens with one of the tags the toolbars produce
# (Quill wraps even one bare word in <p>), so this tells "already rich text"
# from "plain text written before the editors existed, or by a machine".
_RICH_TEXT_MARKER = re.compile(
	r'<(?:%s)(?:\s[^>]*)?/?>' % '|'.join(sorted(CREATOR_HTML_ALLOWED_TAGS)),
	re.IGNORECASE,
)


def coerce_creator_html(raw):
	"""Store `raw` as creator HTML, whatever it is today.

	These fields now render `|safe`, and they hold two kinds of value: rich text
	from an editor, and plain text from every path that predates one — old rows,
	old ZIP exports, AI-generated drafts. Escaping the second kind is what keeps
	a literal "takes <5 minutes" on the page instead of silently eating it (nh3
	would drop `<5 minutes` as an unknown tag).

	Returns '' for falsy input.
	"""
	if not raw:
		return ''
	text = str(raw)
	if _RICH_TEXT_MARKER.search(text):
		return sanitize_creator_html(text)
	return escape(text)
