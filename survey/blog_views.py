"""Public blog, article pages, the public changelog and their RSS feeds
(change public-blog-and-changelog, issue #647). The data lives in `survey/blog.py` and
`survey/changelog.py`; these views only pick and render it.
"""
import datetime
import json

from django.http import Http404, HttpResponse
from django.shortcuts import render
from django.templatetags.static import static
from django.utils.feedgenerator import Rss201rev2Feed

from . import blog, changelog
from .embedding import public_base_url
from .seo_landings import HOME, SITE_ORIGIN, Crumb, build_breadcrumb_jsonld

BLOG_CRUMB = Crumb("Blog", "/blog/")
CHANGELOG_CRUMB = Crumb("Changelog", "/changelog/")
BLOG_FEED_SIZE = 20
CHANGELOG_FEED_SIZE = 30


def _is_staff(request):
    return request.user.is_authenticated and request.user.is_staff


def blog_index(request):
    """/blog/ -- stories and articles in one grid. `?kind=` narrows to one kind; the chips are
    plain links and the canonical stays /blog/, so a filter mints no indexable duplicate."""
    every = blog.feed_items()
    present = {item.filter for item in every}
    chips = [(value, label) for value, label in blog.filters() if value in present]
    active = request.GET.get('kind', '')
    if active not in present:
        active = ''
    items = [item for item in every if not active or item.filter == active]
    return render(request, 'blog_index.html', {
        'items': items,
        'kind_chips': chips if len(chips) > 1 else [],
        'active_kind': active,
        'breadcrumb_jsonld': build_breadcrumb_jsonld((HOME, BLOG_CRUMB)),
    })


def _article_jsonld(article):
    data = {
        "@context": "https://schema.org",
        "@type": "BlogPosting",
        "headline": article.title,
        "description": article.summary,
        "url": f"{SITE_ORIGIN}{article.url}",
        "mainEntityOfPage": f"{SITE_ORIGIN}{article.url}",
        "datePublished": article.date.isoformat(),
        "dateModified": (article.updated or article.date).isoformat(),
        "author": ({"@type": "Organization", "name": "Mapsurvey", "url": SITE_ORIGIN}
                   if article.author == blog.DEFAULT_AUTHOR
                   else {"@type": "Person", "name": article.author}),
        "publisher": {"@type": "Organization", "name": "Mapsurvey", "url": SITE_ORIGIN},
    }
    if article.cover:
        data["image"] = f"{SITE_ORIGIN}{static(article.cover)}"
    return json.dumps(data, ensure_ascii=False)


def blog_post(request, slug):
    article = blog.by_slug(slug)
    if article is None or (article.draft and not _is_staff(request)):
        raise Http404
    from .topics import chips_for   # reads `.topics`, which an article has too
    topic_chips = chips_for(article)
    entries = {entry.id: entry for entry in changelog.entries()}
    return render(request, 'blog_post.html', {
        'article': article,
        'body_html': blog.render_body(article),
        'is_draft_preview': article.draft,
        'canonical': f"{SITE_ORIGIN}{article.url}",
        'topic_chips': topic_chips,
        'changelog_entries': [entries[i] for i in article.changelog if i in entries],
        'article_jsonld': _article_jsonld(article),
        'breadcrumb_jsonld': build_breadcrumb_jsonld(
            (HOME, BLOG_CRUMB, Crumb(article.title, article.url))),
    })


def changelog_public(request):
    """/changelog/ -- every changelog entry, newest first, for anyone. Editor links ("Open") and
    hero chips stay in the editor: they point at pages a visitor cannot open."""
    articles = blog.article_map()
    rows = [{'entry': entry, 'article': articles.get(entry.id)} for entry in changelog.entries()]
    return render(request, 'changelog_public.html', {
        'rows': rows,
        'breadcrumb_jsonld': build_breadcrumb_jsonld((HOME, CHANGELOG_CRUMB)),
    })


def _rss(feed):
    return HttpResponse(feed.writeString('utf-8'), content_type='application/rss+xml; charset=utf-8')


def _pubdate(day):
    return datetime.datetime.combine(day, datetime.time(9, 0), tzinfo=datetime.timezone.utc)


def blog_feed(request):
    """RSS 2.0 of the newest articles and stories. Links use the host the public reached us on
    (`public_base_url`), not `request.scheme`, which is http behind the proxy."""
    base = public_base_url(request)
    feed = Rss201rev2Feed(
        title="Mapsurvey blog", link=f"{base}/blog/", feed_url=f"{base}/blog/feed.xml",
        description="Features, ideas and customer stories from Mapsurvey.", language="en")
    for item in blog.feed_items()[:BLOG_FEED_SIZE]:
        feed.add_item(title=item.title, link=f"{base}{item.url}", unique_id=f"{base}{item.url}",
                      description=item.summary, pubdate=_pubdate(item.date),
                      categories=[blog.STORY_FILTER[0] if item.kind == 'story' else item.article.label])
    return _rss(feed)


def changelog_feed(request):
    base = public_base_url(request)
    feed = Rss201rev2Feed(
        title="Mapsurvey changelog", link=f"{base}/changelog/", feed_url=f"{base}/changelog/feed.xml",
        description="What changed in Mapsurvey, newest first.", language="en")
    for entry in changelog.entries()[:CHANGELOG_FEED_SIZE]:
        link = f"{base}/changelog/#{entry.id}"
        feed.add_item(title=entry.title, link=link, unique_id=link, description=entry.body,
                      pubdate=_pubdate(entry.day), categories=['Fixed' if entry.kind == 'fixed' else 'New'])
    return _rss(feed)
