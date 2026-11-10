"""Tests for the `budget-question` capability (openspec/specs/budget-question/spec.md,
change budget-question, #447): the settings record, the item extras, what a
section POST stores and refuses for Split and Projects, the budget GROUP over
priced map questions, the Pro gate, the structural-edit rule, the one aggregate
and every read surface."""
import json

from django.contrib.auth.models import User
from django.http import QueryDict
from django.test import TestCase

from billing.tests.helpers import make_sub, trial_used_elsewhere
from survey import budget, budget_stats
from survey.models import (
    Answer, Membership, PublicResultsBlock, PublicResultsPage, Question, QuestionGroup, SurveyHeader,
    SurveySection, SurveySession,
)
from survey.question_types import GEO_TYPES, geo_column, normalise_choice_extras
from survey.services import questions as svc_questions
from survey.services.context import Actor
from survey.services.errors import ProRequired, StructureLocked, ValidationFailed
from survey.tests.helpers import _make_org

SPLIT = {'mode': 'split', 'total': 20000000, 'symbol': '£', 'step': 500000, 'rule': 'all'}
ITEMS = [{'code': 1, 'name': 'Parks'}, {'code': 2, 'name': 'Safety'}, {'code': 3, 'name': 'Youth'}]


def _point(code, lng, lat):
    return json.dumps({'type': 'Feature', 'geometry': {'type': 'Point', 'coordinates': [lng, lat]},
                       'properties': {'question_id': code}})


def _line(code, coords):
    return json.dumps({'type': 'Feature', 'geometry': {'type': 'LineString', 'coordinates': coords},
                       'properties': {'question_id': code}})


class _BudgetFixture(TestCase):
    def setUp(self):
        self.org = _make_org('Budget Org')
        self.user = User.objects.create_user('budget_owner', password='pass')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.survey = SurveyHeader.objects.create(name='budget_survey', organization=self.org,
                                                  created_by=self.user, status='published')
        self.section = SurveySection.objects.create(survey_header=self.survey, name='s1', code='S1',
                                                    is_head=True, layout='map')
        self.actor = Actor(user=self.user, ip='198.51.100.7')

    def _question(self, input_type='budget', settings=SPLIT, choices=ITEMS, code='B1'):
        return Question.objects.create(
            survey_section=self.section, code=code, name='Spend the fund', input_type=input_type,
            order_number=1, choices=[dict(c) for c in choices],
            validation_settings={'budget': budget.normalise_budget_settings(settings, input_type)})

    def _post(self, data):
        return self.client.post(f'/surveys/{self.survey.uuid}/s1/', data)

    def _stored(self, question):
        return Answer.objects.filter(question=question, parent_answer_id__isnull=True)


class BudgetSettingsTest(TestCase):
    def test_settings_are_normalised_by_one_validator(self):
        """
        GIVEN a raw record with string numbers and no rule
        WHEN it is normalised
        THEN numbers are numbers, the rule defaults to all and the source to list
        """
        clean = budget.normalise_budget_settings({'total': '20,000,000', 'step': '500000', 'symbol': ' £ '})
        self.assertEqual(clean['total'], 20000000)
        self.assertEqual(clean['step'], 500000)
        self.assertEqual(clean['symbol'], '£')
        self.assertEqual((clean['mode'], clean['rule'], clean['source']), ('split', 'all', 'list'))

    def test_step_larger_than_total_is_refused_naming_the_step(self):
        """
        GIVEN a step greater than the total
        WHEN the record is normalised
        THEN it is refused and the error names the step
        """
        with self.assertRaises(budget.BudgetSettingsError) as ctx:
            budget.normalise_budget_settings({'total': 10, 'step': 20})
        self.assertEqual(ctx.exception.field, 'step')

    def test_percent_fixes_the_total_and_drops_the_symbol(self):
        """
        GIVEN unit percent with a total of 50 and a symbol
        WHEN the record is normalised
        THEN the total is 100 and the symbol is empty
        """
        clean = budget.normalise_budget_settings({'unit': 'percent', 'total': 50, 'symbol': '£'})
        self.assertEqual((clean['total'], clean['symbol']), (100, ''))

    def test_projects_never_require_spending_it_all(self):
        """
        GIVEN a Projects record that asks for rule all
        WHEN it is normalised
        THEN the rule is upto
        """
        self.assertEqual(budget.normalise_budget_settings({'mode': 'projects', 'total': 5, 'rule': 'all'})['rule'], 'upto')

    def test_amounts_read_the_same_everywhere(self):
        """
        GIVEN currency, points and percent records
        WHEN amounts are formatted
        THEN millions and thousands are short and units are named
        """
        cur = budget.normalise_budget_settings({'total': 20000000, 'symbol': '£'})
        self.assertEqual(budget.format_amount(20000000, cur), '£20M')
        self.assertEqual(budget.format_amount(2500000, cur), '£2.5M')
        self.assertEqual(budget.format_amount(500000, cur), '£500k')
        self.assertEqual(budget.format_amount(35, {'unit': 'points'}), '35 pts')
        self.assertEqual(budget.format_amount(40, {'unit': 'percent'}), '40%')

    def test_item_extras_are_capped_not_rejected(self):
        """
        GIVEN an item with a 500-character description, a string cost and a bad cap
        WHEN choice extras are normalised
        THEN the description is 300 characters, the cost a number and the cap dropped
        """
        choices = normalise_choice_extras([{'code': 1, 'name': 'a', 'description': 'x' * 500,
                                            'cost': '2,500', 'max_count': 0}])
        self.assertEqual(len(choices[0]['description']), 300)
        self.assertEqual(choices[0]['cost'], 2500)
        self.assertNotIn('max_count', choices[0])

    def test_budget_is_not_a_geo_type_and_no_geo_type_was_added(self):
        """
        GIVEN the type registry
        WHEN the budget type is looked up
        THEN it is not geo, and the geo types are the four the map knows
        """
        self.assertNotIn('budget', GEO_TYPES)
        self.assertEqual(set(GEO_TYPES), {'point', 'line', 'polygon', 'spraycan'})

    def test_a_price_is_per_what_the_type_can_measure(self):
        """
        GIVEN prices per mark, per metre and per square metre
        WHEN they are normalised for a point, a line and an area
        THEN a point keeps only per mark, a line per metre, an area per square metre
        """
        self.assertEqual(budget.normalise_price({'amount': 2000, 'per': 'feature'}, 'point'), {'amount': 2000, 'per': 'feature'})
        self.assertIsNone(budget.normalise_price({'amount': 50, 'per': 'length'}, 'point'))
        self.assertEqual(budget.normalise_price({'amount': '50', 'per': 'length'}, 'line')['per'], 'length')
        self.assertEqual(budget.normalise_price({'amount': 30, 'per': 'area'}, 'polygon')['per'], 'area')
        self.assertIsNone(budget.normalise_price({'amount': 0}, 'point'))

    def test_group_budget_has_no_step_and_no_mode(self):
        """
        GIVEN a group budget record
        WHEN it is normalised
        THEN it holds the total, unit and symbol only
        """
        clean = budget.normalise_budget_settings({'total': 60000, 'symbol': '£', 'step': 5}, budget.GROUP)
        self.assertEqual(clean, {'unit': 'currency', 'total': 60000, 'symbol': '£'})

    def test_measures_follow_the_servers_projection(self):
        """
        GIVEN a 1 km east-west line and a 100 m square at 53.6°N
        WHEN measured per metre and per square metre
        THEN the length is about 1000 m and the area about 10 000 m²
        """
        from django.contrib.gis.geos import LineString, Polygon
        import math
        lat = 53.6
        dlng = 1000 / (111320 * math.cos(math.radians(lat)))
        line = LineString((0, lat), (dlng, lat), srid=4326)
        self.assertAlmostEqual(budget.measure(line, 'length'), 1000, delta=15)
        side = 100 / (111320 * math.cos(math.radians(lat)))
        dlat = 100 / 111320
        square = Polygon(((0, lat), (side, lat), (side, lat + dlat), (0, lat + dlat), (0, lat)), srid=4326)
        self.assertAlmostEqual(budget.measure(square, 'area'), 10000, delta=200)


class SplitSubmissionTest(_BudgetFixture):
    def test_split_is_stored_as_one_allocation(self):
        """
        GIVEN a Split question with a £20M budget and rule all
        WHEN a respondent allocates 12M, 6M and 2M
        THEN one answer holds the allocation with its total and no selected choices
        """
        q = self._question()
        self._post({'B1__1': '12000000', 'B1__2': '6000000', 'B1__3': '2000000'})
        answer = self._stored(q).get()
        self.assertEqual(answer.allocation, {'total': 20000000, 'items': {'1': 12000000, '2': 6000000, '3': 2000000}})
        self.assertIsNone(answer.selected_choices)

    def test_short_of_the_whole_budget_stores_nothing(self):
        """
        GIVEN rule all
        WHEN a POST allocates 15.5M of 20M
        THEN no answer is stored and the section still submits
        """
        q = self._question()
        response = self._post({'B1__1': '15500000'})
        self.assertNotEqual(response.status_code, 500)
        self.assertFalse(self._stored(q).exists())

    def test_off_step_and_over_budget_store_nothing(self):
        """
        GIVEN a £0.5M step and rule upto
        WHEN a POST sends an amount off the step, and another one over the budget
        THEN neither is stored
        """
        q = self._question(settings={**SPLIT, 'rule': 'upto'})
        self._post({'B1__1': '1200000'})
        self.assertFalse(self._stored(q).exists())
        self._post({'B1__1': '20000000', 'B1__2': '500000'})
        self.assertFalse(self._stored(q).exists())

    def test_amounts_come_back_on_revisit(self):
        """
        GIVEN a stored allocation
        WHEN the respondent opens the section again
        THEN each amount input carries the stored amount
        """
        self._question()
        self._post({'B1__1': '12000000', 'B1__2': '6000000', 'B1__3': '2000000'})
        content = self.client.get(f'/surveys/{self.survey.uuid}/s1/').content.decode()
        self.assertIn('name="B1__1" value="12000000"', content)
        self.assertIn('data-budget-config', content)


class ProjectsSubmissionTest(_BudgetFixture):
    PROJECTS = [{'code': 1, 'name': 'Hub', 'cost': 8000000}, {'code': 2, 'name': 'Crossings', 'cost': 2500000},
                {'code': 3, 'name': 'Pool', 'cost': 12000000}]

    def test_picked_projects_store_their_costs(self):
        """
        GIVEN a Projects question with a £20M budget
        WHEN a respondent picks the hub and the crossings, plus an unknown code
        THEN the allocation holds the two known projects at their costs
        """
        q = self._question(settings={'mode': 'projects', 'total': 20000000}, choices=self.PROJECTS)
        self._post({'B1': ['1', '2', '99']})
        self.assertEqual(self._stored(q).get().allocation,
                         {'total': 20000000, 'items': {'1': 8000000, '2': 2500000}})

    def test_over_budget_is_refused_server_side(self):
        """
        GIVEN a crafted POST picking 22.5M of a 20M budget
        WHEN it is submitted
        THEN no answer is stored
        """
        q = self._question(settings={'mode': 'projects', 'total': 20000000}, choices=self.PROJECTS)
        self._post({'B1': ['1', '2', '3']})
        self.assertFalse(self._stored(q).exists())


class BudgetGroupTest(_BudgetFixture):
    """A budget group over ordinary map questions (spec budget-question
    "A budget group bounds the marks of its priced map questions")."""

    def _park(self, total=10000):
        self.group = QuestionGroup.objects.create(
            survey_section=self.section, title='Improve the park', order_number=1,
            budget=budget.normalise_budget_settings({'total': total, 'symbol': '£'}, budget.GROUP))
        self.bench = Question.objects.create(
            survey_section=self.section, code='BENCH', name='Benches', input_type='point', order_number=2,
            group=self.group, validation_settings={'price': {'amount': 2000, 'per': 'feature'}})
        self.path = Question.objects.create(
            survey_section=self.section, code='PATH', name='Paths', input_type='line', order_number=3,
            group=self.group, validation_settings={'price': {'amount': 5, 'per': 'length'}})
        self.free = Question.objects.create(
            survey_section=self.section, code='FREE', name='Anything else', input_type='point', order_number=4,
            group=self.group)

    def test_the_page_carries_the_bar_and_the_prices(self):
        """
        GIVEN a budget group with a priced point and a priced line
        WHEN the section renders
        THEN the group shows the budget bar and each priced button carries its price and caption
        """
        self._park()
        content = self.client.get(f'/surveys/{self.survey.uuid}/s1/').content.decode()
        self.assertIn('data-budget-group=', content)
        self.assertIn('data-price-amount="2000" data-price-per="feature"', content)
        self.assertIn('£2\u202f000 each', content)
        self.assertIn('£5 / m', content)

    def test_marks_are_admitted_in_stored_order_until_the_budget_is_spent(self):
        """
        GIVEN a £10k budget, benches at £2k each and paths at £5 a metre
        WHEN a POST places four benches and a 1 km path
        THEN the benches (£8k) stay and the path (£5k) is dropped; a free mark always stays
        """
        import math
        self._park()
        dlng = 1000 / (111320 * math.cos(math.radians(53.6)))
        self._post({
            'BENCH': '|'.join(_point('BENCH', 0.001 * i, 53.6) for i in range(4)) + '|',
            'PATH': _line('PATH', [[0, 53.6], [dlng, 53.6]]) + '|',
            'FREE': _point('FREE', 0, 53.6) + '|',
        })
        self.assertEqual(self._stored(self.bench).count(), 4)
        self.assertEqual(self._stored(self.path).count(), 0)
        self.assertEqual(self._stored(self.free).count(), 1)

    def test_a_short_path_fits(self):
        """
        GIVEN £10k and a 200 m path at £5 a metre
        WHEN it is posted with one bench
        THEN both are stored and the export carries each mark's cost
        """
        import math
        self._park()
        dlng = 200 / (111320 * math.cos(math.radians(53.6)))
        self._post({'BENCH': _point('BENCH', 0, 53.6) + '|', 'PATH': _line('PATH', [[0, 53.6], [dlng, 53.6]]) + '|'})
        self.assertEqual(self._stored(self.path).count(), 1)
        from survey.export import _geo_layer
        layer = _geo_layer(self.survey, self.path, set())
        self.assertAlmostEqual(layer.collection['features'][0]['properties']['cost'], 1000, delta=20)

    def test_group_aggregate_counts_measures_and_spend(self):
        """
        GIVEN two respondents with benches and one with a path
        WHEN the group aggregate is computed
        THEN benches count ×3 and £6k, the path its metres and cost, respondents 2
        """
        import math
        self._park()
        dlng = 200 / (111320 * math.cos(math.radians(53.6)))
        s1 = SurveySession.objects.create(survey=self.survey)
        s2 = SurveySession.objects.create(survey=self.survey)
        from django.contrib.gis.geos import LineString, Point
        for s, n in ((s1, 2), (s2, 1)):
            for i in range(n):
                Answer.objects.create(survey_session=s, question=self.bench, point=Point(0.001 * i, 53.6, srid=4326))
        Answer.objects.create(survey_session=s2, question=self.path, line=LineString((0, 53.6), (dlng, 53.6), srid=4326))
        agg = budget_stats.group_aggregate(self.group)
        by = {e['code']: e for e in agg['items']}
        self.assertEqual(agg['respondents'], 2)
        self.assertEqual((by['BENCH']['count'], by['BENCH']['cost']), (3, 6000))
        self.assertAlmostEqual(by['PATH']['measure'], 200, delta=5)
        self.assertEqual(by['FREE']['cost'], 0)

    def test_the_create_picker_offers_a_budget_group_card_in_map_questions(self):
        """
        GIVEN the New question modal of a map section, and of a form section
        WHEN the type picker is rendered
        THEN the map section offers a "Budget group" card as an action, the form section greys it out,
             and an existing question's type picker never shows it
        """
        self.client.force_login(self.user)
        self.survey.status = 'draft'
        self.survey.save()
        html = self.client.get(f'/editor/surveys/{self.survey.uuid}/sections/{self.section.id}/questions/new/').content.decode()
        self.assertIn('data-qtp-action="budget_group"', html)
        form_section = SurveySection.objects.create(survey_header=self.survey, name='f', code='F1', layout='form')
        html = self.client.get(f'/editor/surveys/{self.survey.uuid}/sections/{form_section.id}/questions/new/').content.decode()
        self.assertIn('data-qtp-unavailable="budget_group"', html)
        q = self._question()
        html = self.client.get(f'/editor/surveys/{self.survey.uuid}/questions/{q.id}/edit/').content.decode()
        self.assertNotIn('data-qtp-action="budget_group"', html)

    def test_the_card_creates_a_budget_group_and_opens_its_own_modal(self):
        """
        GIVEN a Free workspace and the picker's Budget group card
        WHEN it posts to the group endpoint with budget=1 and a title
        THEN a group with a budget exists, titled from the typed name, and the modal is the budget one
        """
        self.client.force_login(self.user)
        self.survey.status = 'draft'
        self.survey.save()
        response = self.client.post(f'/editor/surveys/{self.survey.uuid}/sections/{self.section.id}/groups/new/',
                                    {'budget': '1', 'title': 'Park improvements'})
        self.assertEqual(response.status_code, 200)
        group = QuestionGroup.objects.get(survey_section=self.section)
        self.assertEqual((group.title, group.budget['total']), ('Park improvements', 10000))
        html = response.content.decode()
        self.assertIn('Budget group', html)
        self.assertIn('Map questions inside carry the price.', html)
        self.assertNotIn('data-tip-for="plain"', html)

    def test_a_group_budget_is_free_on_every_plan(self):
        """
        GIVEN a Free workspace whose owner used their trial elsewhere
        WHEN a budget is set on a group
        THEN it saves, with no Pro refusal and no trial started
        """
        from billing.models import EntitlementGrant
        from survey.services import groups as svc_groups
        self.survey.status = 'draft'
        self.survey.save()
        group = QuestionGroup.objects.create(survey_section=self.section, title='Park', order_number=1)
        trial_used_elsewhere(self.org)
        group = svc_groups.update(self.actor, group, {'budget_present': '1', 'budget_total': '60000',
                                                      'budget_unit': 'currency', 'budget_symbol': '£'})
        self.assertEqual(group.budget['total'], 60000)
        self.assertFalse(EntitlementGrant.objects.filter(organization=self.org).exists())

    def test_changing_a_live_groups_total_is_structural_and_a_price_too(self):
        """
        GIVEN a published survey with a budget group and a priced bench question
        WHEN the group's total, then the bench's price, are changed in place
        THEN both are refused as structural; renaming the group is not
        """
        from survey.services import groups as svc_groups
        self._park()
        make_sub(self.org)
        with self.assertRaises(StructureLocked):
            svc_groups.update(self.actor, self.group, {'budget_present': '1', 'budget_total': '99999',
                                                        'budget_unit': 'currency', 'budget_symbol': '£'})
        self.group.refresh_from_db()
        svc_groups.update(self.actor, self.group, {'title': 'Pilgrim Park'})
        base = {'name': 'Benches', 'input_type': 'point', 'color': '#000000', 'display_style': 'default',
                'vs_price_amount': '2000', 'vs_price_per': 'feature'}
        svc_questions.update(self.actor, self.bench, base)
        self.bench.refresh_from_db()
        with self.assertRaises(StructureLocked):
            svc_questions.update(self.actor, self.bench, {**base, 'vs_price_amount': '3000'})

    def test_budget_and_price_round_trip_the_archive(self):
        """
        GIVEN a budget group with a priced line
        WHEN the section's groups and the question are serialised and re-created
        THEN the budget and the price survive
        """
        from survey.serialization import _create_groups, _create_question, _serialize_groups, _serialize_question
        self._park()
        groups_data = _serialize_groups(self.section, None)
        self.assertEqual(groups_data[0]['budget']['total'], 10000)
        other = SurveySection.objects.create(survey_header=self.survey, name='s2', code='S2')
        index = {}
        _create_groups(other, None, groups_data, index)
        copy = QuestionGroup.objects.get(survey_section=other)
        self.assertEqual(copy.budget['total'], 10000)
        data = _serialize_question(self.path)
        self.assertEqual(data['price'], {'amount': 5, 'per': 'length'})
        q = _create_question(other, data, [], {}, warnings=[])
        self.assertEqual(q.validation_settings['price'], {'amount': 5, 'per': 'length'})


class BudgetServiceTest(_BudgetFixture):
    def _data(self, **extra):
        return {'name': 'Fund', 'input_type': 'budget', 'color': '#000000', 'display_style': 'default',
                'vs_budget_mode': 'projects', 'vs_budget_total': '100', 'vs_budget_unit': 'points',
                'choices_json': json.dumps([{'code': 1, 'name': 'A', 'cost': 40}, {'code': 2, 'name': 'B'}]),
                **extra}

    def setUp(self):
        super().setUp()
        self.survey.status = 'draft'
        self.survey.save()

    def test_a_project_without_a_cost_is_refused_naming_it(self):
        """
        GIVEN a Projects budget whose second item has no cost
        WHEN it is saved through the service
        THEN the save is refused and the message names the item
        """
        with self.assertRaises(ValidationFailed) as ctx:
            svc_questions.create(self.actor, self.section, self._data())
        self.assertIn('“B”', ctx.exception.message)

    def test_split_items_need_no_cost(self):
        """
        GIVEN a Split budget with items without costs
        WHEN it is saved
        THEN it is created with the normalised record
        """
        q = svc_questions.create(self.actor, self.section, self._data(vs_budget_mode='split', vs_budget_step='5'))
        self.assertEqual(q.validation_settings['budget']['mode'], 'split')
        self.assertEqual(q.validation_settings['budget']['step'], 5)

    def test_a_layer_sourced_budget_needs_pro(self):
        """
        GIVEN a Free workspace whose owner used their trial elsewhere
        WHEN a budget whose items are a layer's objects is saved
        THEN the service refuses with pro_required
        """
        from survey.tests.helpers import _objects_layer
        trial_used_elsewhere(self.org)
        layer = _objects_layer(self.survey)
        data = self._data(vs_budget_source='layer', vs_budget_cost_property='cost', layer=str(layer.pk), choices_json='')
        with self.assertRaises(ProRequired):
            svc_questions.create(self.actor, self.section, data)

    def test_changing_the_total_of_a_live_budget_is_structural(self):
        """
        GIVEN a published Split question
        WHEN its total is changed in place
        THEN the service raises StructureLocked; renaming an item is not
        """
        self.survey.status = 'published'
        self.survey.save()
        q = self._question(settings={**SPLIT, 'rule': 'upto'})
        base = {'name': q.name, 'input_type': 'budget', 'color': '#000000', 'display_style': 'default',
                'vs_budget_mode': 'split', 'vs_budget_total': '20000000', 'vs_budget_step': '500000',
                'vs_budget_symbol': '£', 'vs_budget_rule': 'upto',
                'choices_json': json.dumps(ITEMS)}
        with self.assertRaises(StructureLocked):
            svc_questions.update(self.actor, q, {**base, 'vs_budget_total': '25000000'})
        q.refresh_from_db()   # the refused save left its values on the instance
        renamed = [dict(ITEMS[0], name='Green spaces')] + ITEMS[1:]
        svc_questions.update(self.actor, q, {**base, 'choices_json': json.dumps(renamed)})


class BudgetAggregateTest(_BudgetFixture):
    def _answer(self, q, allocation):
        session = SurveySession.objects.create(survey=self.survey)
        Answer.objects.create(survey_session=session, question=q, allocation=allocation)
        return session

    def test_shares_use_each_answers_own_total(self):
        """
        GIVEN one answer of 10 of 20 to Parks and one of 10 of 40
        WHEN the Split aggregate is computed
        THEN Parks' mean share is (0.5 + 0.25) / 2
        """
        q = self._question(settings={**SPLIT, 'total': 20, 'step': 1, 'rule': 'upto'})
        self._answer(q, {'total': 20, 'items': {'1': 10}})
        self._answer(q, {'total': 40, 'items': {'1': 10}})
        parks = budget_stats.aggregate(q)['items'][0]
        self.assertAlmostEqual(parks['mean_share'], 0.375)
        self.assertEqual(parks['n'], 2)

    def test_the_set_that_fits_takes_support_order(self):
        """
        GIVEN projects supported 71/64/58/52/40/30 % costing 8, 2.5, 1.5, 5, 3, 1 under 19
        WHEN the fitting set is computed
        THEN it is the first four and the sixth: the fifth does not fit, the cheaper sixth still does
        """
        entries = [{'code': str(i), 'cost': c, 'n': 1, 'pick_share': s}
                   for i, (c, s) in enumerate([(8, .71), (2.5, .64), (1.5, .58), (5, .52), (3, .40), (1, .30)], 1)]
        self.assertEqual(budget_stats.fitting_set(entries, 19), ['1', '2', '3', '4', '6'])

    def test_small_items_are_masked_on_the_public_page(self):
        """
        GIVEN K=3 and one respondent who gave Youth anything
        WHEN the public budget block is built
        THEN Youth is masked and Parks is not
        """
        q = self._question(settings={**SPLIT, 'total': 20, 'step': 1, 'rule': 'upto'})
        for _ in range(3):
            self._answer(q, {'total': 20, 'items': {'1': 10}})
        self._answer(q, {'total': 20, 'items': {'1': 5, '3': 5}})
        page = PublicResultsPage.objects.create(survey=self.survey, slug='budget-pr', is_published=True)
        block = PublicResultsBlock.objects.create(page=page, block_type='budget', question=q, order=0)
        from survey.public_results import PublicResultsService
        payload = PublicResultsService(page)._build_block(block)
        rows = {r['name']: r for r in payload['budget']['rows']}
        self.assertTrue(rows['Youth']['masked'])
        self.assertFalse(rows['Parks']['masked'])


class BudgetExportTest(_BudgetFixture):
    def test_split_exports_one_column_per_item_and_a_total(self):
        """
        GIVEN a Split allocation
        WHEN its export cells are built
        THEN each item has an amount column with the symbol, and a total follows
        """
        from survey.export import budget_cells
        q = self._question()
        cells = budget_cells(q, {'total': 20000000, 'items': {'1': 15000000, '2': 5000000}})
        self.assertEqual(cells['Spend the fund: Parks (£)'], 15000000)
        self.assertEqual(cells['Spend the fund: Youth (£)'], 0)
        self.assertEqual(cells['Spend the fund: total (£)'], 20000000)

    def test_projects_export_one_or_zero(self):
        """
        GIVEN a Projects allocation picking item 2
        WHEN its export cells are built
        THEN item 2 is 1 and the others 0
        """
        from survey.export import budget_cells
        q = self._question(settings={'mode': 'projects', 'total': 10},
                           choices=[dict(c, cost=3) for c in ITEMS])
        cells = budget_cells(q, {'total': 10, 'items': {'2': 3}})
        self.assertEqual((cells['Spend the fund: Parks'], cells['Spend the fund: Safety']), (0, 1))


class BudgetSerializationTest(_BudgetFixture):
    def test_settings_and_extras_round_trip(self):
        """
        GIVEN a Projects budget with descriptions and costs
        WHEN the survey is serialised and its question re-created from the archive data
        THEN the settings and the item extras survive
        """
        from survey.serialization import _create_question, _serialize_question
        q = self._question(settings={'mode': 'projects', 'total': 100, 'unit': 'points'},
                           choices=[{'code': 1, 'name': 'A', 'cost': 40, 'description': 'First'}])
        data = _serialize_question(q)
        other = SurveySection.objects.create(survey_header=self.survey, name='s2', code='S2')
        warnings = []
        copy = _create_question(other, data, [], {}, warnings=warnings)
        self.assertEqual(copy.validation_settings['budget']['mode'], 'projects')
        self.assertEqual(copy.choices[0]['cost'], 40)
        self.assertEqual(copy.choices[0]['description'], 'First')
        self.assertEqual(warnings, [])

    def test_missing_layer_falls_back_to_a_list(self):
        """
        GIVEN archive data for a layer-sourced budget with no layer in the archive
        WHEN it is imported
        THEN it imports as a typed list with a report line
        """
        from survey.serialization import _create_question
        data = {'code': 'B9', 'name': 'x', 'input_type': 'budget', 'choices': [],
                'budget': {'mode': 'projects', 'total': 10, 'source': 'layer', 'cost_property': 'cost'}, 'layer': 0}
        warnings = []
        copy = _create_question(self.section, data, [], {}, warnings=warnings, layer_ids=[])
        self.assertEqual(copy.validation_settings['budget']['source'], 'list')
        self.assertTrue(any('typed list' in w for w in warnings))


class BudgetPrintTest(_BudgetFixture):
    def test_the_budget_type_has_a_paper_shape_and_a_priced_mark_says_its_price(self):
        """
        GIVEN the printable form's shape registry and a priced point under a budget group
        WHEN the budget type is looked up and the point's shape is built
        THEN the type has its own shape and the point's note names the price
        """
        from survey.print.pdf import QUESTION_SHAPES, shape_geo, shape_unknown
        self.assertIsNot(QUESTION_SHAPES.get('budget', shape_unknown), shape_unknown)
        from types import SimpleNamespace
        group = QuestionGroup.objects.create(
            survey_section=self.section, title='Park', order_number=1,
            budget=budget.normalise_budget_settings({'total': 10000, 'symbol': '£'}, budget.GROUP))
        q = Question.objects.create(survey_section=self.section, code='B9', name='Bench', input_type='point',
                                    order_number=2, group=group, validation_settings={'price': {'amount': 2000, 'per': 'feature'}})
        from survey.print import register_fonts
        from survey.print.pdf import _styles
        register_fonts()
        ctx = SimpleNamespace(letters={q.id: 'A'}, styles=_styles(), lang='en')
        texts = [getattr(f, 'text', '') for f in shape_geo(q, ctx)]
        self.assertTrue(any('£2' in t and 'each' in t for t in texts), texts)


class BudgetTranslationTest(_BudgetFixture):
    def test_item_descriptions_are_rows_in_the_translation_table(self):
        """
        GIVEN a two-language survey with a described budget item
        WHEN the translation occurrences are listed
        THEN the description is a row keyed by the item's code, and writing it stores it per language
        """
        from survey import translation_table
        self.survey.available_languages = ['en', 'de']
        self.survey.save()
        q = self._question(choices=[{'code': 1, 'name': 'Parks', 'description': 'Green spaces'}])
        keys = [o.key for o in translation_table.occurrences(self.survey, 'de')]
        self.assertIn('question:B1:choice:1:description', keys)
        svc_questions.set_choice_descriptions(q, 'de', {'1': 'Grünflächen'})
        q.refresh_from_db()
        self.assertEqual(q.choices[0]['description_i18n'], {'de': 'Grünflächen'})
        self.assertEqual(budget.items_of(q, 'de')[0]['description'], 'Grünflächen')
