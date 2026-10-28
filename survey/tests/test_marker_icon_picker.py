"""Tests for the `marker-icon-picker` capability (openspec/specs/marker-icon-picker/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase, SimpleTestCase
from django.contrib.auth.models import User
from survey.models import SurveyHeader, SurveySection, Question, Membership
import os
from survey import marker_icons as _marker_icons
from survey.tests.helpers import _make_org


class MarkerIconCatalogTest(SimpleTestCase):
    """The generated catalog and sprites keep the shape the picker and resolver rely on."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.catalog = _marker_icons.catalog()
        import os
        base = os.path.join(os.path.dirname(_marker_icons.__file__), 'assets', 'img')
        cls.sprites = {}
        for name in _marker_icons.SVG_SETS:
            with open(os.path.join(base, '%s.svg' % name), encoding='utf-8') as fh:
                cls.sprites[name] = fh.read()

    def test_catalog_has_every_set_and_no_brands(self):
        """
        GIVEN the committed catalog
        WHEN it is loaded
        THEN it holds Font Awesome, Maki and Temaki entries and no `fab ` brand icon
        """
        values = [i['v'] for i in self.catalog['icons']]
        self.assertTrue(any(v.startswith('fas fa-') for v in values))
        self.assertTrue(any(v.startswith('far fa-') for v in values))
        self.assertTrue(any(v.startswith('maki:') for v in values))
        self.assertTrue(any(v.startswith('temaki:') for v in values))
        self.assertFalse([v for v in values if v.startswith('fab ')])
        self.assertGreater(len(values), 1500)

    def test_every_entry_is_complete_and_categorised(self):
        """
        GIVEN the catalog
        WHEN each icon is inspected
        THEN it carries value, label, declared categories and English terms
        """
        declared = {c['id'] for c in self.catalog['categories']}
        for icon in self.catalog['icons']:
            self.assertTrue(icon['v'] and icon['l'] and icon['c'] and icon['t'].get('en'), icon)
            for cat in icon['c']:
                self.assertIn(cat, declared, icon['v'])
        for cat in self.catalog['categories']:
            self.assertIn('en', cat['label'])

    def test_map_set_values_have_sprite_symbols_without_fill(self):
        """
        GIVEN every maki:/temaki: value in the catalog
        WHEN its sprite is searched
        THEN the symbol exists and no symbol carries a fill attribute
        """
        for icon in self.catalog['icons']:
            if ':' not in icon['v']:
                continue
            set_name, name = icon['v'].split(':', 1)
            self.assertIn('id="%s-%s"' % (set_name, name), self.sprites[set_name], icon['v'])
        for name, sheet in self.sprites.items():
            self.assertNotIn(' fill=', sheet, name)

    def test_gzipped_catalog_stays_under_the_ceiling(self):
        """
        GIVEN the catalog file
        WHEN gzipped as WhiteNoise would serve it
        THEN it stays under 350 KB so translation tables cannot balloon unnoticed
        """
        import gzip
        with open(_marker_icons.CATALOG_PATH, 'rb') as fh:
            size = len(gzip.compress(fh.read()))
        self.assertLess(size, 350 * 1024, size)

    def test_translated_terms_reach_the_catalog(self):
        """
        GIVEN the bus stop and bench icons
        WHEN their terms are read
        THEN each product language has a translation (the tables were merged at build time)
        """
        by_value = {i['v']: i for i in self.catalog['icons']}
        bench = by_value['temaki:bench']
        for lang in self.catalog['languages']:
            self.assertIn(lang, bench['t'], lang)
        self.assertIn('скамейк', bench['t']['ru'])
        self.assertIn('bank', bench['t']['de'])
        self.assertIn('bus', by_value['fas fa-bus']['t']['en'])


class MarkerIconEditorValidationTest(TestCase):
    """QuestionForm.clean_icon_class — what a creator may save."""

    def setUp(self):
        self.org = _make_org()
        self.user = User.objects.create_user(username='iconeditor', password='pass')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.client.login(username='iconeditor', password='pass')
        self.survey = SurveyHeader.objects.create(name='icon_test', visibility='private', organization=self.org)
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='sec1', title='Section 1', code='S1', is_head=True,
        )
        self.url = f'/editor/surveys/{self.survey.uuid}/sections/{self.section.id}/questions/new/'

    def _post(self, icon):
        return self.client.post(self.url, {
            'name': 'Where?', 'input_type': 'point', 'color': '#000000', 'icon_class': icon,
        })

    def test_pasted_font_awesome_class_saves(self):
        """
        GIVEN a creator types a Font Awesome class the picker never listed
        WHEN the question is created
        THEN the value is stored as typed
        """
        self._post('fas fa-anchor')
        self.assertEqual(Question.objects.get(name='Where?').icon_class, 'fas fa-anchor')

    def test_map_set_value_saves(self):
        """
        GIVEN a creator picks a Maki icon
        WHEN the question is created
        THEN the prefixed value is stored
        """
        self._post('maki:bus')
        self.assertEqual(Question.objects.get(name='Where?').icon_class, 'maki:bus')

    def test_unknown_map_set_name_is_rejected(self):
        """
        GIVEN a creator mistypes a map icon name
        WHEN the form is submitted
        THEN nothing is stored and the response carries a field error naming the accepted forms
        """
        response = self._post('maki:benchh')
        self.assertFalse(Question.objects.filter(name='Where?').exists())
        self.assertIn('maki:bus', response.content.decode())

    def test_legacy_v4_class_still_saves(self):
        """
        GIVEN an existing question holding a Font Awesome 4 class
        WHEN the creator saves an unrelated change
        THEN the save succeeds and the value is unchanged
        """
        q = Question.objects.create(
            survey_section=self.section, name='Old', code='q_old', input_type='point',
            order_number=1, icon_class='fa fa-bus',
        )
        self.client.post(f'/editor/surveys/{self.survey.uuid}/questions/{q.id}/edit/', {
            'name': 'Old renamed', 'input_type': 'point', 'color': '#000000', 'icon_class': 'fa fa-bus',
        })
        q.refresh_from_db()
        self.assertEqual(q.name, 'Old renamed')
        self.assertEqual(q.icon_class, 'fa fa-bus')
