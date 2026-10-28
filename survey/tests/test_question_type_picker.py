"""Tests for the `question-type-picker` capability (openspec/specs/question-type-picker/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase
from django.contrib.auth.models import User
from survey.models import SurveyHeader, SurveySection, Question, Membership
from survey.tests.helpers import _make_org


class QuestionTypePickerMetadataTest(TestCase):
    """Picker metadata (survey/question_types.py) stays in step with the model."""

    def test_metadata_covers_every_input_type(self):
        """
        GIVEN the model's INPUT_TYPE_CHOICES and the picker's PICKER_TYPES
        WHEN their key sets are compared
        THEN they are identical, so a type added to the model without picker
             metadata fails here instead of silently missing from the dialog
        """
        from survey.models import INPUT_TYPE_CHOICES
        from survey.question_types import PICKER_TYPES

        model_types = {value for value, _ in INPUT_TYPE_CHOICES}
        self.assertEqual(model_types, set(PICKER_TYPES.keys()))

    def test_every_type_belongs_to_exactly_one_known_group(self):
        """
        GIVEN the picker metadata
        WHEN each entry's group is checked against PICKER_GROUPS
        THEN every type names a declared group
        """
        from survey.question_types import PICKER_GROUPS, PICKER_TYPES

        group_keys = {key for key, _ in PICKER_GROUPS}
        for value, meta in PICKER_TYPES.items():
            self.assertIn(meta["group"], group_keys, f"{value} has unknown group")

    def test_html_reads_formatted_text_but_keeps_its_value(self):
        """
        GIVEN the html input type
        WHEN the picker groups are built from the model choices
        THEN the card is labelled "Formatted Text" while its value stays html
        """
        from survey.models import INPUT_TYPE_CHOICES
        from survey.question_types import picker_groups_for

        groups = dict(picker_groups_for(INPUT_TYPE_CHOICES))
        display_blocks = groups["Display blocks — collect nothing"]
        html_entry = next(t for t in display_blocks if t["value"] == "html")
        self.assertEqual(html_entry["label"], "Formatted Text")

    def test_groups_respect_restricted_choice_sets(self):
        """
        GIVEN a restricted choices list (as a sub-question's form field has)
        WHEN picker groups are built from it
        THEN excluded types are absent and emptied groups are dropped
        """
        from survey.question_types import picker_groups_for

        groups = picker_groups_for([("text", "Text"), ("number", "Number")])
        self.assertEqual(len(groups), 1)
        label, types = groups[0]
        self.assertEqual(label, "Questions")
        self.assertEqual({t["value"] for t in types}, {"text", "number"})


class QuestionPreviewLiveTest(TestCase):
    """The question dialog's live preview renders unsaved drafts server-side."""

    def setUp(self):
        self.org = _make_org('PreviewLiveOrg')
        self.owner = User.objects.create_user('qpl_owner', password='pw')
        Membership.objects.create(user=self.owner, organization=self.org, role='owner')
        self.survey = SurveyHeader.objects.create(
            name='qpl_survey', organization=self.org, created_by=self.owner, status='draft',
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='s1', title='S1', code='S1', is_head=True,
        )
        self.url = f'/editor/surveys/{self.survey.uuid}/sections/{self.section.id}/question-preview/'
        self.client.force_login(self.owner)
        session = self.client.session
        session['active_org_id'] = self.org.id
        session.save()

    def test_rating_draft_renders_choices_without_saving(self):
        """
        GIVEN an unsaved rating draft with two labelled choices
        WHEN the modal posts it to the live preview endpoint
        THEN the response is the respondent-side radio rendering of those
             choices AND no Question row was created
        """
        before = Question.objects.count()
        response = self.client.post(self.url, {
            'input_type': 'rating',
            'name': 'How much do you like apples?',
            'choices_json': '[{"code": 1, "name": "worst"}, {"code": 5, "name": "best"}]',
        })
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('How much do you like apples?', html)
        self.assertIn('worst', html)
        self.assertIn('best', html)
        self.assertIn('type="radio"', html)
        self.assertEqual(Question.objects.count(), before)

    def test_geo_draft_carries_colour_and_icon(self):
        """
        GIVEN an unsaved point draft with a colour and icon class
        WHEN it is posted to the live preview endpoint
        THEN the draw button renders with that colour and icon
        """
        response = self.client.post(self.url, {
            'input_type': 'point',
            'name': 'Where is your fruit market?',
            'color': '#d9534f',
            'icon_class': 'fas fa-store',
        })
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('data-color="#d9534f"', html)
        self.assertIn('fas fa-store', html)

    def test_range_draft_uses_choice_codes_as_bounds(self):
        """
        GIVEN an unsaved range draft with codes 2 and 8
        WHEN it is posted to the live preview endpoint
        THEN the slider renders with min 2 and max 8
        """
        response = self.client.post(self.url, {
            'input_type': 'range',
            'name': 'Ripeness',
            'choices_json': '[{"code": 2, "name": "green"}, {"code": 8, "name": "brown"}]',
        })
        html = response.content.decode()
        self.assertIn('min="2"', html)
        self.assertIn('max="8"', html)

    def test_malformed_choices_fall_back_instead_of_erroring(self):
        """
        GIVEN a draft whose choices_json is mid-edit garbage
        WHEN it is posted to the live preview endpoint
        THEN the endpoint renders the type's no-choices fallback, not a 500
        """
        for bad in ('{not json', '"a string"', '[{"name": "no code"}]',
                    '[{"code": "NaN", "name": "x"}]', '[42]'):
            response = self.client.post(self.url, {
                'input_type': 'rating',
                'name': 'Q',
                'choices_json': bad,
            })
            self.assertEqual(response.status_code, 200, f'choices_json={bad!r}')

    def test_unknown_input_type_is_rejected(self):
        """
        GIVEN a draft naming an input type the model does not have
        WHEN it is posted to the live preview endpoint
        THEN the request is rejected with 400, not rendered
        """
        # Not 'ranking': that was the example when this test was written and
        # it is a real type now, which is the happiest way for a test to fail.
        response = self.client.post(self.url, {'input_type': 'telepathy', 'name': 'Q'})
        self.assertEqual(response.status_code, 400)

    def test_display_style_reaches_the_render(self):
        """
        GIVEN a rating draft with the labelled-list display style
        WHEN it is posted to the live preview endpoint
        THEN the response renders through the list style, one row per choice
        """
        response = self.client.post(self.url, {
            'input_type': 'rating',
            'name': 'Q',
            'display_style': 'list_pips',
            'choices_json': '[{"code": 1, "name": "worst"}, {"code": 2, "name": "best"}]',
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('rating-list-pips', response.content.decode())

    def test_anonymous_request_is_refused(self):
        """
        GIVEN no authenticated session
        WHEN the live preview endpoint is posted to
        THEN the request does not render the preview
        """
        self.client.logout()
        response = self.client.post(self.url, {'input_type': 'text', 'name': 'Q'})
        self.assertNotEqual(response.status_code, 200)


class PickerUnavailableTypesTest(TestCase):
    def test_unavailable_types_come_back_disabled(self):
        """
        GIVEN choices without the map types and an `unavailable` map for two of them
        WHEN picker groups are built
        THEN the Map questions group holds exactly those two, disabled with the reason,
             and the enabled types carry no reason
        """
        from survey.question_types import picker_groups_for
        groups = dict(picker_groups_for(
            [('text', 'Text'), ('choice', 'Choices')],
            {'point': ('Geo Point', 'No map'), 'line': ('Geo Line', 'No map')},
        ))
        geo = groups['Map questions']
        self.assertEqual([t['value'] for t in geo], ['point', 'line'])
        self.assertTrue(all(t['disabled'] and t['reason'] == 'No map' for t in geo))
        self.assertEqual(geo[0]['label'], 'Geo Point')
        self.assertFalse(any(t['disabled'] for t in groups['Questions']))
