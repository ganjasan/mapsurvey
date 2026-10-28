"""Tests for the `marker-icon-rendering` capability (openspec/specs/marker-icon-rendering/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase, SimpleTestCase, Client
from django.contrib.auth.models import User
from io import BytesIO
from survey.models import SurveyHeader, SurveySection, Question, Membership
from survey.serialization import export_survey_to_zip, import_survey_from_zip
import os
from survey import marker_icons as _marker_icons
from survey.tests.helpers import _make_org


class MarkerIconResolverTest(SimpleTestCase):
    """survey/marker_icons.py — the one place an icon_class value becomes markup."""

    def test_font_awesome_values_pass_through(self):
        """
        GIVEN a Font Awesome-shaped value, listed or not
        WHEN resolved
        THEN it is a font glyph with the value as its class list
        """
        self.assertEqual(_marker_icons.resolve('fas fa-bus'), {'kind': 'font', 'classes': 'fas fa-bus'})
        self.assertEqual(_marker_icons.resolve('fas fa-some-pro-icon'),
                         {'kind': 'font', 'classes': 'fas fa-some-pro-icon'})
        self.assertEqual(_marker_icons.resolve(''), {'kind': 'font', 'classes': _marker_icons.DEFAULT_PIN})

    def test_map_set_value_resolves_to_symbol(self):
        """
        GIVEN a catalogued maki: value
        WHEN resolved
        THEN it is an svg glyph naming the sprite symbol
        """
        self.assertEqual(_marker_icons.resolve('maki:bus'), {'kind': 'svg', 'set': 'maki', 'symbol': 'maki-bus'})

    def test_unknown_map_set_value_falls_back_to_the_pin(self):
        """
        GIVEN a temaki: value no sprite knows
        WHEN resolved
        THEN the default pin is drawn instead of a blank glyph
        """
        self.assertEqual(_marker_icons.resolve('temaki:does-not-exist'),
                         {'kind': 'font', 'classes': _marker_icons.DEFAULT_PIN})

    def test_validation_accepts_both_forms_and_legacy(self):
        """
        GIVEN values of every accepted shape
        WHEN validated
        THEN empty, Font Awesome (v4 or v5, listed or not) and catalogued svg names pass; typos and garbage fail
        """
        for ok in ('', '  ', 'fas fa-anchor', 'far fa-circle', 'fa fa-bus', 'fas fa-some-pro-icon', 'maki:bus', 'temaki:bench'):
            self.assertTrue(_marker_icons.is_valid(ok), ok)
        for bad in ('maki:benchh', 'temaki:', 'garbage', 'fas', 'bus', '<script>'):
            self.assertFalse(_marker_icons.is_valid(bad), bad)

    def test_render_markup(self):
        """
        GIVEN the template tag's renderer
        WHEN a font and an svg value are drawn with a colour
        THEN the font is an <i> coloured via color: and the svg a <use> of the hashed sprite filled via fill:
        """
        font = _marker_icons.render('fas fa-bus', color='#123456', css_class='feature-icon')
        self.assertIn('<i class="fas fa-bus feature-icon"', font)
        self.assertIn('color:#123456', font)
        svg = _marker_icons.render('maki:bus', color='#123456', css_class='feature-icon')
        self.assertIn('<svg class="marker-icon-svg-glyph feature-icon"', svg)
        self.assertIn('fill:#123456', svg)
        self.assertRegex(svg, r'<use href="/static[a-z]*/img/maki(\.[0-9a-f]+)?\.svg#maki-bus"')

    def test_render_escapes_a_hostile_value(self):
        """
        GIVEN a value carrying markup (the form rejects it, the DB might still hold it)
        WHEN rendered
        THEN it is escaped, not injected
        """
        out = _marker_icons.render('fas fa-x" onmouseover="alert(1)')
        self.assertNotIn('onmouseover="alert', out)
        self.assertIn('&quot;', out)


class MarkerIconRenderingTest(TestCase):
    """Every respondent-facing surface draws the icon through the resolver."""

    def setUp(self):
        self.org = _make_org()
        self.user = User.objects.create_user('iconrender', password='pass')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')

    def _survey(self, input_type, icon_class, **extra):
        survey = SurveyHeader.objects.create(
            name=f'icons_{input_type}_{id(self)}', organization=self.org,
            created_by=self.user, status='published',
        )
        section = SurveySection.objects.create(survey_header=survey, name='s1', code='S1', is_head=True)
        Question.objects.create(
            survey_section=section, name='Where?', code='q_geo', input_type=input_type,
            order_number=1, color='#336699', icon_class=icon_class, **extra,
        )
        return survey

    def _page(self, survey):
        return Client().get(f'/surveys/{survey.uuid}/s1/').content.decode()

    def test_map_set_point_question_renders_svg_everywhere(self):
        """
        GIVEN a point question with a Temaki icon
        WHEN a respondent opens the section
        THEN the draw button draws an <svg><use> of the Temaki symbol, keeps the raw value in data-icon,
             and the body exposes the sprite URLs for the browser resolver
        """
        html = self._page(self._survey('point', 'temaki:bench'))
        self.assertIn('data-icon="temaki:bench"', html)
        self.assertIn('#temaki-bench"', html)
        self.assertIn('<use href=', html)
        self.assertIn('fill:#336699', html)
        self.assertIn('data-icon-sprites=', html)
        self.assertRegex(html, r'/static[a-z]*/img/maki')

    def test_font_awesome_point_question_renders_as_before(self):
        """
        GIVEN a point question with a Font Awesome icon
        WHEN a respondent opens the section
        THEN the draw button holds <i class="fas fa-bus …"> and the page never prepends a bare `fa ` prefix
        """
        html = self._page(self._survey('point', 'fas fa-bus'))
        self.assertIn('<i class="fas fa-bus', html)
        self.assertIn('data-icon="fas fa-bus"', html)
        self.assertNotIn("'fa ' +", html)
        self.assertNotIn("fa ' + ", html)

    def test_star_rating_with_map_set_icon(self):
        """
        GIVEN a stars rating whose icon is maki:star and colour blue
        WHEN a respondent opens the section
        THEN five sprite glyphs render instead of five <i> tags
        """
        choices = [{"code": i, "name": {"en": str(i)}} for i in range(1, 6)]
        survey = self._survey('rating', 'maki:star', display_style='stars', choices=choices)
        html = self._page(survey)
        self.assertEqual(html.count('#maki-star"'), 5)
        self.assertIn('--star-color: #336699', html)

    def test_base_templates_load_the_catalog_font_awesome_version(self):
        """
        GIVEN the three base templates
        WHEN their sources are read
        THEN each loads Font Awesome 5.15.4 and none the old 5.8.1
        """
        import os
        base = os.path.join(os.path.dirname(_marker_icons.__file__), 'templates')
        for rel in ('base.html', 'base_survey_template.html', 'editor/editor_base.html'):
            with open(os.path.join(base, rel), encoding='utf-8') as fh:
                src = fh.read()
            self.assertIn('fontawesome.com/releases/v5.15.4/', src, rel)
            self.assertNotIn('v5.8.1', src, rel)

    def test_editor_modal_exposes_catalog_and_language_and_no_inline_list(self):
        """
        GIVEN the survey editor page
        WHEN it renders for a creator
        THEN the modal body carries the catalog URL and UI language, and the old inline icon array is gone
        """
        self.client.login(username='iconrender', password='pass')
        survey = self._survey('point', 'temaki:bench')
        survey.status = 'draft'
        survey.save()
        html = self.client.get(f'/editor/surveys/{survey.uuid}/').content.decode()
        self.assertRegex(html, r'data-icon-catalog="/static[a-z]*/data/icon_catalog')
        self.assertIn('data-icon-lang="en"', html)
        self.assertIn('js/icon_picker', html)
        self.assertNotIn('var FA_ICONS', html)


class MarkerIconSerializationTest(TestCase):
    """icon_class rides ZIP export/import verbatim, in both value forms."""

    def setUp(self):
        self.org = _make_org()
        self.user = User.objects.create_user('iconzip', password='pass')

    def _roundtrip(self, icon_class):
        survey = SurveyHeader.objects.create(name=f'zip_{id(self)}', organization=self.org, created_by=self.user)
        section = SurveySection.objects.create(survey_header=survey, name='s1', code='S1', is_head=True)
        Question.objects.create(
            survey_section=section, name='Where?', code='q_geo', input_type='point',
            order_number=1, icon_class=icon_class,
        )
        out = BytesIO()
        export_survey_to_zip(survey, out, mode='structure')
        out.seek(0)
        imported, _warnings = import_survey_from_zip(out, organization=self.org, created_by=self.user)
        return Question.objects.get(survey_section__survey_header=imported, name='Where?').icon_class

    def test_map_set_value_survives_export_and_import(self):
        """
        GIVEN a question with icon_class maki:bench
        WHEN it is exported and the archive imported
        THEN the imported question stores maki:bench
        """
        self.assertEqual(self._roundtrip('maki:bench'), 'maki:bench')

    def test_unknown_value_is_preserved(self):
        """
        GIVEN an archive carrying a map icon name the catalog does not know
        WHEN imported
        THEN import succeeds and the value is stored unchanged (it renders the fallback pin)
        """
        self.assertEqual(self._roundtrip('temaki:future-icon'), 'temaki:future-icon')
