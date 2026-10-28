"""Tests for the `story-topics` capability (openspec/specs/story-topics/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase, Client
import json
from survey.models import Story
import tempfile
from django.core.management import call_command


class StoryTopicsTest(TestCase):
    """Story topics tie a story to the landing page it proves (change story-topics, #250)."""

    def _story(self, slug, topics, published=True):
        from django.utils import timezone as tz
        return Story.objects.create(
            title=slug.replace('-', ' ').title(), slug=slug, story_type='case-study',
            is_published=published, published_date=tz.now(), topics=topics)

    # --- registry ---------------------------------------------------------------------

    def test_registry_is_consistent(self):
        """
        GIVEN the topic registry
        WHEN its landing keys are checked against the SEO landing registry
        THEN every landing key names a real landing and no two topics share one
        """
        from survey.topics import TOPICS
        from survey.seo_landings import get_landing
        keys = [t.landing_key for t in TOPICS if t.landing_key]
        self.assertEqual(len(keys), len(set(keys)))
        for key in keys:
            get_landing(key)

    def test_seed_story_refuses_an_unknown_topic(self):
        """
        GIVEN a story.json whose topics carry a slug absent from the registry
        WHEN seed_story reads it
        THEN it fails naming the slug and installs nothing
        """
        import json
        import tempfile
        from pathlib import Path
        from django.core.management import call_command, CommandError
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / 'bad-topic'
            d.mkdir()
            (d / 'story.json').write_text(json.dumps({'title': 'Bad', 'topics': ['no-such-topic']}))
            (d / 'body.html').write_text('<p>x</p>')
            with self.assertRaises(CommandError) as ctx:
                call_command('seed_story', 'bad-topic', '--from', str(d))
        self.assertIn('no-such-topic', str(ctx.exception))
        self.assertFalse(Story.objects.filter(slug='bad-topic').exists())

    def test_seed_story_stores_known_topics_in_order(self):
        """
        GIVEN a story.json with two registry topics
        WHEN seed_story installs it
        THEN the row carries that list in that order
        """
        import json
        import tempfile
        from pathlib import Path
        from django.core.management import call_command
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / 'two-topics'
            d.mkdir()
            (d / 'story.json').write_text(json.dumps(
                {'title': 'Two', 'topics': ['community-engagement', 'parks-public-space']}))
            (d / 'body.html').write_text('<p>x</p>')
            call_command('seed_story', 'two-topics', '--from', str(d))
        self.assertEqual(Story.objects.get(slug='two-topics').topics,
                         ['community-engagement', 'parks-public-space'])

    def test_shipped_story_data_carries_registry_topics_only(self):
        """
        GIVEN every story.json in survey/story_data
        WHEN its topics are validated
        THEN each slug is in the registry
        """
        import json
        import pathlib
        from survey.topics import validate_slugs
        root = pathlib.Path(__file__).resolve().parent.parent / 'story_data'
        for meta in root.glob('*/story.json'):
            validate_slugs(json.loads(meta.read_text(encoding='utf-8')).get('topics', []))

    def test_admin_form_rejects_an_unknown_topic(self):
        """
        GIVEN the story admin form
        WHEN topics contain a slug absent from the registry
        THEN the form is invalid and names the slug
        """
        from survey.admin import StoryAdminForm
        story = self._story('admin-story', [])
        form = StoryAdminForm(instance=story, data={
            'title': story.title, 'slug': story.slug, 'story_type': 'case-study',
            'body': '', 'topics': '["nope"]', 'facts': '[]', 'is_published': True})
        self.assertFalse(form.is_valid())
        self.assertIn('nope', str(form.errors['topics']))

    # --- story page -----------------------------------------------------------------

    def test_story_page_links_topics_with_a_landing(self):
        """
        GIVEN a published story tagged community-engagement and citizen-science
        WHEN its page is rendered
        THEN the first chip links to /community-engagement-platform/ and the second is plain text
        """
        self._story('linked', ['community-engagement', 'citizen-science'])
        body = Client().get('/stories/linked/').content.decode()
        self.assertIn('<a href="/community-engagement-platform/">Community engagement</a>', body)
        self.assertIn('<span>Citizen science</span>', body)

    def test_story_page_without_topics_has_no_chip_row(self):
        """
        GIVEN a published story with no topics
        WHEN its page is rendered
        THEN no chip row is rendered
        """
        self._story('bare', [])
        self.assertNotContains(Client().get('/stories/bare/'), 'sd-topics')

    # --- index filter ----------------------------------------------------------------

    def test_index_filter_limits_the_grid_and_keeps_the_canonical(self):
        """
        GIVEN four published stories, two tagged parks-public-space
        WHEN /stories/?topic=parks-public-space is requested
        THEN only those two are listed, the chip is active and the canonical is /stories/
        """
        self._story('park-one', ['parks-public-space'])
        self._story('park-two', ['parks-public-space', 'local-government'])
        self._story('plan', ['neighbourhood-plan'])
        self._story('none', [])
        body = Client().get('/stories/?topic=parks-public-space').content.decode()
        self.assertIn('/stories/park-one/', body)
        self.assertIn('/stories/park-two/', body)
        self.assertNotIn('/stories/plan/', body)
        self.assertNotIn('/stories/none/', body)
        self.assertRegex(body, r'<a href="/stories/\?topic=parks-public-space" class="is-active"')
        self.assertIn('<link rel="canonical" href="https://mapsurvey.org/stories/">', body)

    def test_index_offers_only_used_topics_and_ignores_unknown_ones(self):
        """
        GIVEN published stories carrying parks-public-space only
        WHEN /stories/?topic=no-such-topic is requested
        THEN every story is shown and the filter row offers Parks but not Citizen science
        """
        self._story('park-one', ['parks-public-space'])
        self._story('plain', [])
        body = Client().get('/stories/?topic=no-such-topic').content.decode()
        self.assertIn('/stories/park-one/', body)
        self.assertIn('/stories/plain/', body)
        self.assertIn('?topic=parks-public-space', body)
        self.assertNotIn('?topic=citizen-science', body)

    # --- landing block ---------------------------------------------------------------

    def test_landing_shows_the_stories_of_its_topic(self):
        """
        GIVEN two published community-engagement stories, one draft and one on another topic
        WHEN /community-engagement-platform/ is rendered
        THEN the From the field block lists exactly the two published ones
        """
        self._story('ce-one', ['community-engagement'])
        self._story('ce-two', ['community-engagement', 'local-government'])
        self._story('ce-draft', ['community-engagement'], published=False)
        self._story('other', ['research'])
        body = Client().get('/community-engagement-platform/').content.decode()
        self.assertIn('id="from-the-field"', body)
        self.assertIn('Community engagement projects built with Mapsurvey', body)
        self.assertIn('/stories/ce-one/', body)
        self.assertIn('/stories/ce-two/', body)
        self.assertNotIn('/stories/ce-draft/', body)
        self.assertNotIn('/stories/other/', body)

    def test_landing_without_matching_stories_has_no_block(self):
        """
        GIVEN no published story tagged education
        WHEN /for-educators/ is rendered
        THEN there is no From the field section
        """
        self._story('other', ['research'])
        self.assertNotContains(Client().get('/for-educators/'), 'id="from-the-field"')

    def test_alternatives_page_renders_no_block(self):
        """
        GIVEN a landing that owns no topic
        WHEN /alternatives/maptionnaire/ is rendered with stories published
        THEN there is no From the field section and the page still renders
        """
        self._story('ce-one', ['community-engagement'])
        response = Client().get('/alternatives/maptionnaire/')
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'id="from-the-field"')
