"""Tests for the `public-results-scaffold` capability (openspec/specs/public-results-scaffold/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.utils import timezone
from unittest.mock import patch
from survey.models import SurveyHeader, SurveySection, Question, Membership, PublicResultsPage, PublicResultsBlock
from io import StringIO
from django.core.management import call_command
from survey.tests.helpers import _make_org


class PublicResultsScaffoldTest(TestCase):
    """Tests for auto-drafting the public results page at publish time."""

    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.client = Client()
        self.org = _make_org('ScaffoldOrg')
        self.owner = User.objects.create_user(username='scaffold_owner', password='pass')
        Membership.objects.create(user=self.owner, organization=self.org, role='owner')
        self.survey = SurveyHeader.objects.create(
            name='scaffold_test', organization=self.org, created_by=self.owner,
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='s1', code='S1', is_head=True,
        )
        self.point_q = Question.objects.create(
            survey_section=self.section, code='Q_PT', name='Mark spot',
            input_type='point', order_number=1,
        )
        self.choice_q = Question.objects.create(
            survey_section=self.section, code='Q_CH', name='Rate',
            input_type='choice', choices=[{'code': 1, 'name': 'Yes'}], order_number=2,
        )
        self.text_q = Question.objects.create(
            survey_section=self.section, code='Q_TX', name='Comment',
            input_type='text', order_number=3,
        )
        self.config_url = f'/editor/surveys/{self.survey.uuid}/public-results/'

    def _publish(self):
        self.client.login(username='scaffold_owner', password='pass')
        response = self.client.post(
            f'/editor/surveys/{self.survey.uuid}/transition/',
            {'status': 'published'}, HTTP_HX_REQUEST='true',
        )
        self.assertEqual(response.status_code, 204)

    def test_first_publish_scaffolds_draft(self):
        """
        GIVEN a draft survey with a point, a choice and a text question
        WHEN the owner publishes it
        THEN a draft results page appears with a map and a chart block in
             survey order, unlisted, unpublished, with anonymous geo popups
        """
        self._publish()
        page = PublicResultsPage.objects.get(survey=self.survey)
        self.assertIsNotNone(page.scaffolded_at)
        self.assertFalse(page.is_published)
        self.assertEqual(page.visibility, 'unlisted')
        blocks = list(page.blocks.all())
        self.assertEqual(
            [(b.block_type, b.question_id) for b in blocks],
            [('map', self.point_q.id), ('chart', self.choice_q.id)],
        )
        self.assertEqual(blocks[0].geo_label_fields, [])

    def test_lazily_created_empty_page_is_populated(self):
        """
        GIVEN a page row that exists with zero blocks (config tab was opened
              while the survey was a draft)
        WHEN the survey is published
        THEN the existing page is populated and stamped
        """
        page = PublicResultsPage.objects.create(survey=self.survey, slug='lazy-page')
        self._publish()
        page.refresh_from_db()
        self.assertIsNotNone(page.scaffolded_at)
        self.assertEqual(page.blocks.count(), 2)
        # The lazily created row carried the model's `public` default; the
        # scaffold must pull it back to unlisted-until-reviewed.
        self.assertEqual(page.visibility, 'unlisted')

    def test_deleted_blocks_are_not_resurrected(self):
        """
        GIVEN a scaffolded page whose blocks the creator deleted
        WHEN the survey is closed and published again
        THEN no blocks are recreated
        """
        self._publish()
        page = PublicResultsPage.objects.get(survey=self.survey)
        page.blocks.all().delete()
        for status in ('closed', 'published'):
            response = self.client.post(
                f'/editor/surveys/{self.survey.uuid}/transition/',
                {'status': status}, HTTP_HX_REQUEST='true',
            )
            self.assertEqual(response.status_code, 204)
        self.assertEqual(page.blocks.count(), 0)

    def test_hand_built_page_is_untouched(self):
        """
        GIVEN a page with creator-built blocks and no scaffold stamp
        WHEN the survey is published
        THEN the existing blocks are unchanged and no defaults are added
        """
        page = PublicResultsPage.objects.create(survey=self.survey, slug='hand-built')
        manual = PublicResultsBlock.objects.create(
            page=page, question=self.choice_q, block_type='chart', viz='pie',
        )
        self._publish()
        page.refresh_from_db()
        self.assertEqual(list(page.blocks.values_list('id', flat=True)), [manual.id])
        self.assertIsNotNone(page.scaffolded_at)

    def test_public_url_stays_gated_after_scaffold(self):
        """
        GIVEN a freshly scaffolded (unpublished) results page
        WHEN a visitor requests /r/<slug>/
        THEN it 404s until the creator publishes the page
        """
        self._publish()
        page = PublicResultsPage.objects.get(survey=self.survey)
        response = self.client.get(f'/r/{page.slug}/')
        self.assertEqual(response.status_code, 404)

    def test_scaffold_failure_does_not_block_transition(self):
        """
        GIVEN the scaffold raising an unexpected error
        WHEN the owner publishes the survey
        THEN the transition still succeeds
        """
        with patch('survey.services.publishing.scaffold_page', side_effect=RuntimeError('boom')):
            self._publish()
        self.survey.refresh_from_db()
        self.assertEqual(self.survey.status, 'published')
        self.assertFalse(PublicResultsPage.objects.filter(survey=self.survey).exists())

    def test_admin_published_survey_scaffolds_on_config_open(self):
        """
        GIVEN a survey whose status was set to published outside the editor
              (e.g. Django admin), so no scaffold ran
        WHEN the creator opens the public-results config tab
        THEN the page renders with scaffolded blocks and the draft banner
        """
        SurveyHeader.objects.filter(pk=self.survey.pk).update(status='published')
        self.client.login(username='scaffold_owner', password='pass')
        response = self.client.get(self.config_url)
        self.assertEqual(response.status_code, 200)
        page = PublicResultsPage.objects.get(survey=self.survey)
        self.assertEqual(page.blocks.count(), 2)
        self.assertIn('We drafted this page from your questions', response.content.decode())

    def test_banner_disappears_after_page_publish(self):
        """
        GIVEN a scaffolded page the creator then publishes
        WHEN the config tab renders
        THEN the draft banner is no longer shown
        """
        self._publish()
        page = PublicResultsPage.objects.get(survey=self.survey)
        page.is_published = True
        page.save()
        response = self.client.get(self.config_url)
        self.assertNotIn('We drafted this page from your questions', response.content.decode())

    def test_config_tab_on_draft_survey_does_not_scaffold(self):
        """
        GIVEN a draft survey
        WHEN the creator opens the config tab
        THEN a page row is lazily created but no blocks are drafted
        """
        self.client.login(username='scaffold_owner', password='pass')
        response = self.client.get(self.config_url)
        self.assertEqual(response.status_code, 200)
        page = PublicResultsPage.objects.get(survey=self.survey)
        self.assertIsNone(page.scaffolded_at)
        self.assertEqual(page.blocks.count(), 0)


class ShareResultsPageLinkTest(TestCase):
    """Tests for the results-page section on the Share page."""

    def setUp(self):
        self.org = _make_org('ShareResOrg')
        self.owner = User.objects.create_user(username='shareres_owner', password='pass')
        Membership.objects.create(user=self.owner, organization=self.org, role='owner')
        self.survey = SurveyHeader.objects.create(
            name='shareres_test', organization=self.org,
            created_by=self.owner, status='published',
        )
        SurveySection.objects.create(
            survey_header=self.survey, name='s1', code='S1', is_head=True,
        )
        self.page = PublicResultsPage.objects.create(
            survey=self.survey, slug='shareres', scaffolded_at=timezone.now(),
        )
        self.share_url = f'/editor/surveys/{self.survey.uuid}/share/'
        self.client.login(username='shareres_owner', password='pass')

    def test_share_links_to_config_while_draft(self):
        """
        GIVEN a published survey with an unpublished results-page draft
        WHEN the Share page renders
        THEN it links to the public-results config tab
        """
        content = self.client.get(self.share_url).content.decode()
        # `&`, not `&amp;`: the label is a msgid now, and gettext output is
        # inserted verbatim — an entity there would ship literally to every
        # other language (see TranslationCatalogHygieneTest).
        self.assertIn('Review & publish the results page', content)
        self.assertIn(f'/editor/surveys/{self.survey.uuid}/public-results/', content)
        # The copyable public link appears only once the page is published
        # (the nav publishing widget may mention the slug regardless).
        self.assertNotIn('id="results-link"', content)

    def test_share_links_to_public_url_once_published(self):
        """
        GIVEN the results page is published
        WHEN the Share page renders
        THEN it shows the public /r/<slug>/ link instead of the config link
        """
        self.page.is_published = True
        self.page.save()
        content = self.client.get(self.share_url).content.decode()
        self.assertIn('id="results-link"', content)
        self.assertIn('/r/shareres/', content)
        self.assertNotIn('Review &amp; publish the results page', content)


class ScaffoldPublicResultsCommandTest(TestCase):
    """Tests for the scaffold_public_results backfill command."""

    def setUp(self):
        self.org = _make_org('ScaffoldCmdOrg')
        self.survey = SurveyHeader.objects.create(
            name='cmd_test', organization=self.org, status='published',
        )
        section = SurveySection.objects.create(
            survey_header=self.survey, name='s1', code='S1', is_head=True,
        )
        Question.objects.create(
            survey_section=section, code='Q_CH', name='Rate',
            input_type='choice', choices=[{'code': 1, 'name': 'Yes'}],
        )

    def _run(self, *args):
        from io import StringIO
        from django.core.management import call_command
        out = StringIO()
        call_command('scaffold_public_results', *args, stdout=out)
        return out.getvalue()

    def test_dry_run_writes_nothing(self):
        """
        GIVEN a published survey without a results page
        WHEN the command runs with --dry-run
        THEN the survey is listed and nothing is created
        """
        output = self._run('--dry-run')
        self.assertIn('would scaffold: cmd_test', output)
        self.assertFalse(PublicResultsPage.objects.filter(survey=self.survey).exists())

    def test_live_run_scaffolds_and_rerun_is_noop(self):
        """
        GIVEN a published survey without a results page
        WHEN the command runs live and then a second time
        THEN the first run scaffolds one block and the second creates nothing
        """
        output = self._run()
        self.assertIn('scaffolded: cmd_test', output)
        page = PublicResultsPage.objects.get(survey=self.survey)
        self.assertEqual(page.blocks.count(), 1)
        output = self._run()
        self.assertIn('Nothing to scaffold', output)
        self.assertEqual(page.blocks.count(), 1)
