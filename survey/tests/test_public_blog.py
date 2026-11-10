"""Tests for the `public-blog` capability (openspec/specs/public-blog/spec.md):
article files, the /blog/ feed over stories and articles, drafts, RSS and the sitemap
(change public-blog-and-changelog, #647). The article text itself is not tested.
"""
import datetime
import os
import tempfile
from unittest import mock

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from survey import blog
from survey.models import Story
from survey.tests.helpers import _ChangelogDirMixin, _ENTRY_A

_POST = """---
title: Budget questions
kind: feature
summary: Residents split the money.
topics: participatory-budgeting
changelog: 2026-09-29-export-formats
---
<p>Body <img src="{static:favicon-32x32.png}" alt=""></p>
"""
_IDEA = """---
title: Why sites
kind: idea
summary: An engagement is longer than a survey.
---
<p>Idea body.</p>
"""
_DRAFT = """---
title: Not yet
kind: feature
summary: Draft.
draft: true
---
<p>Draft body.</p>
"""


class _BlogDirMixin(_ChangelogDirMixin):
    """Point the article loader (and the changelog it validates against) at temp directories."""

    def use_articles(self, files, entries=None):
        self.use_entries(entries if entries is not None else {'2026-09-29-export-formats.html': _ENTRY_A})
        directory = tempfile.mkdtemp()
        for name, text in files.items():
            with open(os.path.join(directory, name), 'w', encoding='utf-8') as fh:
                fh.write(text)
        patcher = mock.patch.object(blog, 'ARTICLES_DIR', directory)
        patcher.start()
        self.addCleanup(patcher.stop)
        blog.clear_cache()
        self.addCleanup(blog.clear_cache)


class BlogArticlesTest(_BlogDirMixin, SimpleTestCase):
    """The article files and their loader."""

    def test_shipped_articles_load(self):
        """
        GIVEN the articles in survey/blog/
        WHEN the loader reads them against the shipped changelog
        THEN every file parses and every changelog id it names is a shipped entry
             (a malformed article fails CI, not a page)
        """
        blog.clear_cache()
        self.addCleanup(blog.clear_cache)
        self.assertTrue(blog.articles())
        self.assertEqual(blog.changelog_problems(), [])
        self.assertEqual(blog.asset_problems(), [])

    def test_missing_static_file_and_help_key_are_reported(self):
        """
        GIVEN an article whose body names a static file that does not exist and an unknown help key
        WHEN the shipped-directory check runs
        THEN both are reported with the file name (production's manifest storage would 500)
        """
        self.use_articles({'2026-11-10-a.html': _POST.replace('favicon-32x32.png', 'img/blog/nope.png')
                           + '<a href="{help:no_such_key}">x</a>\n'})
        self.assertEqual(blog.asset_problems(), ['2026-11-10-a.html: no static file img/blog/nope.png',
                                                 '2026-11-10-a.html: unknown help key no_such_key'])

    def test_unknown_changelog_id_is_reported(self):
        """
        GIVEN an article naming a changelog id that is not an entry
        WHEN the shipped-directory check runs
        THEN it names the file and the id, and the entry map ignores the id
        """
        self.use_articles({'2026-11-10-a.html': _POST.replace('2026-09-29-export-formats', '2026-01-01-nothing')})
        self.assertEqual(blog.changelog_problems(), ['2026-11-10-a.html: 2026-01-01-nothing'])

    def test_valid_article(self):
        """
        GIVEN an article file with the required header keys
        WHEN it is loaded
        THEN slug, date, URL, topics and changelog ids come from the file and {static:} resolves
        """
        self.use_articles({'2026-11-10-budget-questions.html': _POST})
        [article] = blog.articles()
        self.assertEqual(article.slug, 'budget-questions')
        self.assertEqual(article.date, datetime.date(2026, 11, 10))
        self.assertEqual(article.url, '/blog/budget-questions/')
        self.assertEqual(article.topics, ('participatory-budgeting',))
        self.assertEqual(article.author, 'Mapsurvey')
        self.assertIn('favicon-32x32', blog.render_body(article))
        self.assertNotIn('{static:', blog.render_body(article))
        self.assertEqual(blog.article_for_entry('2026-09-29-export-formats'), article)

    def test_refusals_name_the_file(self):
        """
        GIVEN broken article files (unknown topic, bad kind, missing summary, unknown key,
              bad filename, cover without alt)
        WHEN each is loaded
        THEN BlogError names the file
        """
        cases = {
            '2026-11-10-b.html': _POST.replace('participatory-budgeting', 'no-such-topic'),
            '2026-11-10-c.html': _POST.replace('kind: feature', 'kind: guide'),
            '2026-11-10-d.html': _POST.replace('summary: Residents split the money.\n', ''),
            '2026-11-10-e.html': _POST.replace('kind: feature', 'kind: feature\nmood: happy'),
            'budget.html': _POST,
            '2026-11-10-g.html': _POST.replace('kind: feature', 'kind: feature\ncover: x.png'),
        }
        for name, text in cases.items():
            with self.subTest(name=name):
                self.use_articles({name: text})
                with self.assertRaisesMessage(blog.BlogError, name):
                    blog.articles()

    def test_drafts_are_not_published_and_link_no_entry(self):
        """
        GIVEN a draft article naming a changelog entry
        WHEN published articles and the entry map are read
        THEN the draft is in neither
        """
        self.use_articles({'2026-11-10-not-yet.html': _DRAFT.replace(
            'draft: true', 'draft: true\nchangelog: 2026-09-29-export-formats')})
        self.assertEqual(blog.published(), ())
        self.assertIsNone(blog.article_for_entry('2026-09-29-export-formats'))


class BlogPagesTest(_BlogDirMixin, TestCase):
    """/blog/, /blog/<slug>/, the RSS feed and the sitemap."""

    def setUp(self):
        self.use_articles({'2026-11-10-budget-questions.html': _POST,
                           '2026-09-01-why-sites.html': _IDEA,
                           '2026-11-11-not-yet.html': _DRAFT})
        self.story = Story.objects.create(
            title='Olney count', slug='olney', summary='Squirrels.', is_published=True,
            published_date=timezone.make_aware(datetime.datetime(2026, 10, 1)))

    def test_feed_mixes_stories_and_articles_newest_first(self):
        """
        GIVEN a feature article (11-10), a customer story (10-01), an idea (09-01) and a draft
        WHEN a visitor opens /blog/
        THEN the three published items are listed newest first, the story links to /stories/,
             the draft is absent and the chips offer the three kinds
        """
        response = self.client.get('/blog/')
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        positions = [html.index(url) for url in ('/blog/budget-questions/', '/stories/olney/', '/blog/why-sites/')]
        self.assertEqual(positions, sorted(positions))
        self.assertNotIn('/blog/not-yet/', html)
        for value in ('stories', 'features', 'ideas'):
            self.assertIn(f'?kind={value}', html)

    def test_kind_filter_keeps_the_canonical(self):
        """
        GIVEN the same feed
        WHEN a visitor opens /blog/?kind=features
        THEN only the feature article is listed and the canonical is /blog/
        """
        html = self.client.get('/blog/?kind=features').content.decode()
        self.assertIn('/blog/budget-questions/', html)
        self.assertNotIn('/stories/olney/', html)
        self.assertNotIn('/blog/why-sites/', html)
        self.assertIn('<link rel="canonical" href="https://mapsurvey.org/blog/"', html)

    def test_article_page(self):
        """
        GIVEN a published feature article that names a changelog entry and a topic
        WHEN a visitor opens it
        THEN it renders with BlogPosting JSON-LD, the topic chip and the changelog link
        """
        response = self.client.get('/blog/budget-questions/')
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('"@type": "BlogPosting"', html)
        self.assertIn('/changelog/#2026-09-29-export-formats', html)
        self.assertIn('/participatory-budgeting/', html)
        self.assertNotIn('noindex', html)
        self.assertEqual(self.client.get('/blog/no-such-post/').status_code, 404)

    def test_draft_is_staff_only(self):
        """
        GIVEN a draft article
        WHEN an anonymous visitor and then a staff user open it
        THEN the visitor gets 404 and staff see it with noindex
        """
        self.assertEqual(self.client.get('/blog/not-yet/').status_code, 404)
        staff = User.objects.create_user('blogstaff', password='pw', is_staff=True)
        self.client.force_login(staff)
        response = self.client.get('/blog/not-yet/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'noindex, nofollow')

    def test_rss_and_sitemap(self):
        """
        GIVEN the same articles and story
        WHEN the blog RSS and the sitemap are fetched
        THEN both list the published items with absolute links and leave the draft out
        """
        rss = self.client.get('/blog/feed.xml', HTTP_X_FORWARDED_PROTO='https')
        self.assertEqual(rss['Content-Type'], 'application/rss+xml; charset=utf-8')
        body = rss.content.decode()
        self.assertIn('<link>https://testserver/blog/budget-questions/</link>', body)
        self.assertIn('https://testserver/stories/olney/', body)
        self.assertNotIn('not-yet', body)
        sitemap = self.client.get('/sitemap.xml').content.decode()
        for path in ('/blog/<', '/blog/budget-questions/', '/blog/why-sites/', '/changelog/<'):
            self.assertIn(path, sitemap)
        self.assertNotIn('/blog/not-yet/', sitemap)

    def test_chrome_links(self):
        """
        GIVEN any marketing page
        WHEN it renders
        THEN the nav and the footer link the blog and the footer links the changelog
        """
        html = self.client.get('/pricing/').content.decode()
        self.assertGreaterEqual(html.count('href="/blog/"'), 2)
        self.assertIn('href="/changelog/"', html)
