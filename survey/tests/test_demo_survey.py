"""Tests for the `demo-survey` capability (openspec/specs/demo-survey/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase, Client, override_settings
from django.utils import timezone
from survey.models import Organization, SurveyHeader, SurveySection, Question, SurveySession, Answer, PublicResultsPage
from io import StringIO
from django.core.management import call_command
from survey.tests.helpers import _DEMO_MEDIA


@override_settings(MEDIA_ROOT=_DEMO_MEDIA)
class SeedDemoSurveyTest(TestCase):
    """`seed_demo_survey`: the Cycling in Copenhagen demo (change copenhagen-demo)."""

    @classmethod
    def setUpTestData(cls):
        cls.org = Organization.objects.create(name="Demo owner", slug="demo-owner")

    def _seed(self, *args, org='demo-owner'):
        out = StringIO()
        call_command('seed_demo_survey', '--org', org, *args, stdout=out)
        return out.getvalue()

    def _demo(self, org=None):
        from survey.management.commands.seed_demo_survey import survey_name
        return SurveyHeader.objects.get(organization=org or self.org, name=survey_name(), is_canonical=True)

    def test_fresh_install_builds_the_whole_tour(self):
        """
        GIVEN an organisation without the demo
        WHEN seed_demo_survey runs
        THEN a published six-step survey exists with the bridges layer (10 objects, each
             with a photo), a shared layer holding the sample marks, the branching rule,
             star ratings, 40 sessions all tagged `sample`, and a published results page
        """
        from survey.models import LayerObjectAsset
        out = self._seed()
        survey = self._demo()
        self.assertEqual(survey.status, 'published')
        self.assertEqual(SurveySection.objects.filter(survey_header=survey).count(), 6)
        bridges = survey.map_layers.get(source='upload')
        self.assertEqual(bridges.items.count(), 10)
        self.assertEqual(LayerObjectAsset.objects.filter(object__layer=bridges).count(), 10)
        shared = survey.map_layers.get(source='question')
        self.assertGreater(shared.items.count(), 0)
        self.assertTrue(all(o.title for o in shared.items.all()), 'every mark is titled by its problem')
        follow_up = Question.objects.get(survey_section__survey_header=survey,
                                         name='What do you use your bike for?')
        self.assertEqual(follow_up.visibility_rule['choice_codes'], [1, 2])
        rating = Question.objects.get(survey_section__survey_header=survey,
                                      name='How safe do you feel cycling in the city centre?')
        self.assertEqual(rating.display_style, 'stars')
        sessions = SurveySession.objects.filter(survey=survey)
        self.assertEqual(sessions.count(), 40)
        self.assertEqual(sessions.filter(tags__contains=['sample']).count(), 40)
        self.assertTrue(Answer.objects.filter(survey_session__survey=survey,
                                              layer_object__layer=bridges).exists())
        page = PublicResultsPage.objects.get(survey=survey)
        self.assertTrue(page.is_published)
        self.assertEqual(page.slug, 'copenhagen-cycling-demo')
        self.assertEqual(page.visibility, 'unlisted')
        self.assertIn(str(survey.uuid), out)
        self.assertEqual(Client().get('/r/copenhagen-cycling-demo/').status_code, 200)

    def test_second_run_without_replace_changes_nothing(self):
        """
        GIVEN the demo is installed
        WHEN the command runs again without --replace
        THEN no second survey is created and the command says so
        """
        self._seed()
        out = self._seed()
        self.assertIn('already exists', out)
        self.assertEqual(SurveyHeader.objects.filter(organization=self.org).count(), 1)

    def test_replace_reinstalls(self):
        """
        GIVEN the demo is installed
        WHEN the command runs with --replace
        THEN the old survey is gone and a fresh one with 40 sample sessions exists
        """
        self._seed()
        old = self._demo().uuid
        self._seed('--replace')
        new = self._demo()
        self.assertNotEqual(new.uuid, old)
        self.assertFalse(SurveyHeader.objects.filter(uuid=old).exists())
        self.assertEqual(SurveySession.objects.filter(survey=new).count(), 40)

    def test_remapped_codes_still_get_their_answers_and_titles(self):
        """
        GIVEN the demo already exists in another organisation, so its question codes are taken
        WHEN it is installed into a second organisation
        THEN sample answers attach to the second survey's questions, and its shared layer's
             label field follows the remapped code so every mark keeps a title
        """
        other = Organization.objects.create(name="Second", slug="second")
        self._seed()
        self._seed(org='second')
        survey = self._demo(other)
        shared = survey.map_layers.get(source='question')
        why = Question.objects.get(survey_section__survey_header=survey, name='What is the problem?')
        self.assertEqual(shared.label_field, why.code)
        self.assertNotEqual(why.code, 'CPHSPWHY')
        self.assertTrue(shared.items.exists())
        self.assertTrue(all(o.title for o in shared.items.all()))
        self.assertTrue(Answer.objects.filter(survey_session__survey=survey, question=why).exists())

    def test_remove_samples_keeps_real_responses(self):
        """
        GIVEN the demo with sample sessions and one real session with a mark
        WHEN --remove-samples runs
        THEN only the sample sessions and their marks are gone
        """
        self._seed()
        survey = self._demo()
        real = SurveySession.objects.create(survey=survey)
        self._seed('--remove-samples')
        self.assertEqual(list(SurveySession.objects.filter(survey=survey)), [real])
        shared = survey.map_layers.get(source='question')
        self.assertFalse(shared.items.exists())

    def test_sample_sessions_are_not_demo_opens(self):
        """
        GIVEN the demo is the configured demo survey and holds only sample sessions
        WHEN the funnel counts demo opens, then a real visitor opens it
        THEN samples count zero and the visitor counts one
        """
        from datetime import timedelta
        from django.core.cache import cache
        from survey.funnel import AcquisitionService
        self._seed()
        survey = self._demo()
        with self.settings(DEMO_SURVEY_URL=f'https://mapsurvey.org/surveys/{survey.uuid}'):
            cache.clear()
            svc = AcquisitionService(days=60, today=timezone.localdate() + timedelta(days=5))
            self.assertEqual(svc.demo()['stage']['value'], 0)
            SurveySession.objects.create(survey=survey, start_datetime=timezone.now())
            self.assertEqual(svc.demo()['stage']['value'], 1)
