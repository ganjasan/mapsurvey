"""Tests for the `conditional-visibility` capability (openspec/specs/conditional-visibility/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase, Client, override_settings
from django.contrib.auth.models import User
import json
import re
from survey.models import Organization, SurveyHeader, SurveySection, Question, SurveySession, Answer, Membership
from survey.serialization import export_survey_to_zip, import_survey_from_zip
from survey.versioning import clone_survey_for_draft, publish_draft
from survey.cloning import clone_question, clone_section
from survey.tests.helpers import _make_org, _objects_layer, _popup_fixture


class VisibilityEngineTest(TestCase):
    """Tests for survey/visibility.py — the conditional-visibility engine."""

    def _survey(self):
        org = Organization.objects.create(name="Vis Org")
        return SurveyHeader.objects.create(name="vis_survey", organization=org, redirect_url="#")

    def _section(self, survey, name, prev=None, is_head=False, rule=None):
        section = SurveySection.objects.create(
            survey_header=survey, name=name, title=name, code=name[:8],
            is_head=is_head, visibility_rule=rule,
        )
        if prev is not None:
            prev.next_section = section
            prev.save()
            section.prev_section = prev
            section.save()
        return section

    def _choice_q(self, section, code, order=1, input_type='choice', n_options=2, rule=None):
        return Question.objects.create(
            survey_section=section, code=code, order_number=order, name=code,
            input_type=input_type,
            choices=[{"code": i, "name": f"Opt {i}"} for i in range(1, n_options + 1)],
            visibility_rule=rule,
        )

    def setUp(self):
        from survey.visibility import compute_visibility
        self.compute = compute_visibility
        self.survey = self._survey()
        self.s1 = self._section(self.survey, 'intro', is_head=True)
        self.controller = self._choice_q(self.s1, 'CTRL', order=1)

    def test_no_rule_always_visible(self):
        """
        GIVEN a question and section without rules
        WHEN visibility is computed with no answers
        THEN both are visible
        """
        q = self._choice_q(self.s1, 'PLAIN', order=2)
        vmap = self.compute(self.survey, {}, enabled=True)
        self.assertTrue(vmap.is_question_visible(q.id))
        self.assertTrue(vmap.is_section_visible(self.s1.id))

    def test_question_rule_any_of_match(self):
        """
        GIVEN a question shown when CTRL is any of [1, 2]
        WHEN the answer includes code 2
        THEN the question is visible
        """
        q = self._choice_q(self.s1, 'DEP', order=2,
                           rule={"question_code": "CTRL", "choice_codes": [1, 2]})
        vmap = self.compute(self.survey, {"CTRL": [2]}, enabled=True)
        self.assertTrue(vmap.is_question_visible(q.id))

    def test_question_rule_no_match_and_unanswered(self):
        """
        GIVEN a question shown when CTRL = 1
        WHEN CTRL is answered 2, or not answered at all
        THEN the question is hidden
        """
        q = self._choice_q(self.s1, 'DEP', order=2,
                           rule={"question_code": "CTRL", "choice_codes": [1]})
        self.assertFalse(self.compute(self.survey, {"CTRL": [2]}, enabled=True).is_question_visible(q.id))
        self.assertFalse(self.compute(self.survey, {}, enabled=True).is_question_visible(q.id))

    def test_multichoice_controller_intersection(self):
        """
        GIVEN a multichoice controller and a rule on codes [3]
        WHEN the respondent selected [1, 3]
        THEN the dependent is visible
        """
        multi = self._choice_q(self.s1, 'MULTI', order=2, input_type='multichoice', n_options=3)
        q = self._choice_q(self.s1, 'DEP', order=3,
                           rule={"question_code": "MULTI", "choice_codes": [3]})
        vmap = self.compute(self.survey, {"MULTI": [1, 3]}, enabled=True)
        self.assertTrue(vmap.is_question_visible(q.id))

    def test_section_rule_hides_section_and_its_questions(self):
        """
        GIVEN a second section shown when CTRL = 1
        WHEN CTRL is answered 2
        THEN the section, its questions, and the visible chain exclude it
        """
        s2 = self._section(self.survey, 'branch', prev=self.s1,
                           rule={"question_code": "CTRL", "choice_codes": [1]})
        inner = self._choice_q(s2, 'INNER', order=1)
        vmap = self.compute(self.survey, {"CTRL": [2]}, enabled=True)
        self.assertFalse(vmap.is_section_visible(s2.id))
        self.assertFalse(vmap.is_question_visible(inner.id))
        self.assertEqual([s.id for s in vmap.visible_sections], [self.s1.id])

    def test_section_rule_and_question_rule_are_anded(self):
        """
        GIVEN a visible section containing a question whose own rule fails
        WHEN visibility is computed
        THEN the question is hidden while its section stays visible
        """
        s2 = self._section(self.survey, 'branch', prev=self.s1,
                           rule={"question_code": "CTRL", "choice_codes": [1]})
        inner = self._choice_q(s2, 'INNER', order=1,
                               rule={"question_code": "CTRL", "choice_codes": [2]})
        vmap = self.compute(self.survey, {"CTRL": [1]}, enabled=True)
        self.assertTrue(vmap.is_section_visible(s2.id))
        self.assertFalse(vmap.is_question_visible(inner.id))

    def test_cascade_through_hidden_controller(self):
        """
        GIVEN C shown when B = 1, and B shown when A(CTRL) = 1
        WHEN CTRL is answered 2 but a stale B answer of 1 exists
        THEN both B and C are hidden
        """
        b = self._choice_q(self.s1, 'B', order=2,
                           rule={"question_code": "CTRL", "choice_codes": [1]})
        c = self._choice_q(self.s1, 'C', order=3,
                           rule={"question_code": "B", "choice_codes": [1]})
        vmap = self.compute(self.survey, {"CTRL": [2], "B": [1]}, enabled=True)
        self.assertFalse(vmap.is_question_visible(b.id))
        self.assertFalse(vmap.is_question_visible(c.id))

    def test_broken_rule_fails_open(self):
        """
        GIVEN rules referencing a missing question, a non-choice controller,
              a later question, and fully removed option codes
        WHEN visibility is computed
        THEN every broken host is visible and reported in vmap.broken
        """
        text_q = Question.objects.create(
            survey_section=self.s1, code='TXT', order_number=2, name='TXT', input_type='text')
        later = self._choice_q(self.s1, 'LATER', order=10)
        cases = [
            {"question_code": "GONE", "choice_codes": [1]},
            {"question_code": "TXT", "choice_codes": [1]},
            {"question_code": "LATER", "choice_codes": [1]},
            {"question_code": "CTRL", "choice_codes": [99]},
        ]
        hosts = []
        for i, rule in enumerate(cases):
            hosts.append(self._choice_q(self.s1, f'BRK{i}', order=3 + i, rule=rule))
        vmap = self.compute(self.survey, {}, enabled=True)
        for host in hosts:
            self.assertTrue(vmap.is_question_visible(host.id), host.code)
            self.assertIn(("question", host.id), vmap.broken)

    def test_partially_removed_codes_keep_matching(self):
        """
        GIVEN a rule on codes [1, 99] where 99 no longer exists
        WHEN CTRL is answered 1
        THEN the dependent is visible (remaining code still matches)
        """
        q = self._choice_q(self.s1, 'DEP', order=2,
                           rule={"question_code": "CTRL", "choice_codes": [1, 99]})
        vmap = self.compute(self.survey, {"CTRL": [1]}, enabled=True)
        self.assertTrue(vmap.is_question_visible(q.id))
        self.assertNotIn(("question", q.id), vmap.broken)

    def test_section_rule_may_not_reference_own_section(self):
        """
        GIVEN a section whose rule references a question inside itself
        WHEN visibility is computed
        THEN the rule is broken and the section fails open
        """
        s2 = self._section(self.survey, 'selfref', prev=self.s1,
                           rule={"question_code": "SELF", "choice_codes": [1]})
        self._choice_q(s2, 'SELF', order=1)
        vmap = self.compute(self.survey, {}, enabled=True)
        self.assertTrue(vmap.is_section_visible(s2.id))
        self.assertIn(("section", s2.id), vmap.broken)

    def test_kill_switch_returns_all_visible(self):
        """
        GIVEN satisfied-to-hide rules on a question and a section
        WHEN visibility is computed with enabled=False
        THEN everything is visible
        """
        q = self._choice_q(self.s1, 'DEP', order=2,
                           rule={"question_code": "CTRL", "choice_codes": [1]})
        s2 = self._section(self.survey, 'branch', prev=self.s1,
                           rule={"question_code": "CTRL", "choice_codes": [1]})
        vmap = self.compute(self.survey, {}, enabled=False)
        self.assertTrue(vmap.is_question_visible(q.id))
        self.assertTrue(vmap.is_section_visible(s2.id))

    def test_lint_reports_dependents_and_uncovered(self):
        """
        GIVEN two sections covering options 1 of a 3-option controller
        WHEN lint_rules runs
        THEN the controller has 1 dependent and options 2,3 are uncovered
        """
        from survey.visibility import lint_rules
        wide = self._choice_q(self.s1, 'WIDE', order=2, n_options=3)
        self._section(self.survey, 'fan1', prev=self.s1,
                      rule={"question_code": "WIDE", "choice_codes": [1]})
        report = lint_rules(self.survey)
        self.assertEqual(report['dependents'].get(wide.id), 1)
        self.assertEqual(report['uncovered'].get(wide.id), [2, 3])


class ConditionalVisibilityRespondentTest(TestCase):
    """Server-side contract: discard, purge, navigation, progress (openspec:
    conditional-question-visibility)."""

    def setUp(self):
        self.client = Client()
        self.org = Organization.objects.create(name="CondVis Org")
        self.survey = SurveyHeader.objects.create(
            name="condvis", organization=self.org, status='published',
            available_languages=[], redirect_url="#",
        )
        # Section 1: zone choice (3 zones) + albino yes/no + dependent question.
        self.s1 = SurveySection.objects.create(
            survey_header=self.survey, name="pick", title="Your area", code="S1",
            is_head=True,
        )
        self.zone = Question.objects.create(
            survey_section=self.s1, code="ZONE", order_number=1, name="Zone?",
            input_type="choice",
            choices=[{"code": i, "name": f"Area {i}"} for i in (1, 2, 3)],
        )
        self.albino = Question.objects.create(
            survey_section=self.s1, code="ALB", order_number=2, name="Albino?",
            input_type="choice",
            choices=[{"code": 1, "name": "Yes"}, {"code": 0, "name": "No"}],
        )
        self.howmany = Question.objects.create(
            survey_section=self.s1, code="HOW", order_number=3, name="How many?",
            input_type="text_line", required=True,
            visibility_rule={"question_code": "ALB", "choice_codes": [1]},
        )
        # Sections 2 and 3: fan over zones 1 and 2 (zone 3 uncovered).
        self.area1 = SurveySection.objects.create(
            survey_header=self.survey, name="area1", title="Area 1", code="S2",
            visibility_rule={"question_code": "ZONE", "choice_codes": [1]},
        )
        self.a1_notes = Question.objects.create(
            survey_section=self.area1, code="A1N", order_number=1, name="Area 1 notes",
            input_type="text_line",
        )
        self.area2 = SurveySection.objects.create(
            survey_header=self.survey, name="area2", title="Area 2", code="S3",
            visibility_rule={"question_code": "ZONE", "choice_codes": [2]},
        )
        self.a2_notes = Question.objects.create(
            survey_section=self.area2, code="A2N", order_number=1, name="Area 2 notes",
            input_type="text_line",
        )
        # Final unconditional section.
        self.s_final = SurveySection.objects.create(
            survey_header=self.survey, name="final", title="Thanks", code="S4",
        )
        Question.objects.create(
            survey_section=self.s_final, code="FIN", order_number=1, name="Weather",
            input_type="text_line",
        )
        # Linked list: pick -> area1 -> area2 -> final
        self.s1.next_section = self.area1; self.s1.save()
        self.area1.prev_section = self.s1; self.area1.next_section = self.area2; self.area1.save()
        self.area2.prev_section = self.area1; self.area2.next_section = self.s_final; self.area2.save()
        self.s_final.prev_section = self.area2; self.s_final.save()

    def _session(self):
        return SurveySession.objects.get(pk=self.client.session['survey_session_id'])

    def _answers(self, question):
        return Answer.objects.filter(
            survey_session=self._session(), question=question, parent_answer_id__isnull=True)

    def test_tampered_answer_to_hidden_question_is_discarded(self):
        """
        GIVEN HOW is shown only when ALB = Yes
        WHEN the POST answers ALB = No but still carries a HOW value
        THEN no Answer row is stored for HOW
        """
        self.client.get('/surveys/condvis/pick/')
        self.client.post('/surveys/condvis/pick/', {'ZONE': '1', 'ALB': '0', 'HOW': 'ghost'})
        self.assertEqual(self._answers(self.howmany).count(), 0)
        self.assertEqual(self._answers(self.albino).count(), 1)

    def test_geojson_posted_under_a_choice_question_does_not_500(self):
        """
        GIVEN ZONE is stored as a choice question
        WHEN the POST carries pipe-joined GeoJSON under its code, as happens
             when a creator switches a question's type while respondents hold
             the page open
        THEN the submission is processed, the other answers are stored, and no
             500 is raised

        Reproduces the 2026-08-24 incident: 136 ValueErrors, 62 respondents,
        26 minutes — every submit of the section died in the visibility
        pre-pass's `int()`.
        """
        geojson_blob = (
            '{"type":"Feature","properties":{"question_id":"ZONE"},'
            '"geometry":{"type":"Point","coordinates":[-119.35,49.87]}}|'
        )
        self.client.get('/surveys/condvis/pick/')
        response = self.client.post('/surveys/condvis/pick/', {
            'ZONE': geojson_blob, 'ALB': '1', 'HOW': 'two by the tower',
        })
        self.assertEqual(response.status_code, 302)
        # The unreadable controller stores nothing; everything else survives.
        self.assertEqual(self._answers(self.zone).count(), 0)
        self.assertEqual(self._answers(self.albino).get().selected_choices, [1])
        self.assertEqual(self._answers(self.howmany).count(), 1)

    def test_choice_ids_ignores_unparseable_values(self):
        """
        GIVEN a mix of choice identifiers and values that are not identifiers
        WHEN choice_ids parses them
        THEN only the identifiers survive, in order
        """
        from survey.views import choice_ids

        self.assertEqual(choice_ids(['1', '', '{"type":"Feature"}', '0', None]), [1, 0])

    def test_cascade_filled_then_controller_flipped_purges_whole_chain(self):
        """
        GIVEN a filled cascade (ALB=Yes + HOW answered, stored in the DB)
        WHEN the respondent re-submits the section with ALB=No while the POST
             still carries the stale HOW value (exact stale-DOM shape)
        THEN only the flipped controller survives; the whole chain is purged
        """
        self.client.get('/surveys/condvis/pick/')
        self.client.post('/surveys/condvis/pick/', {'ZONE': '1', 'ALB': '1', 'HOW': 'two by the tower'})
        self.assertEqual(self._answers(self.howmany).count(), 1)
        # Flip to No; a stale DOM still posts the old dependent value.
        self.client.post('/surveys/condvis/pick/', {'ZONE': '1', 'ALB': '0', 'HOW': 'two by the tower'})
        self.assertEqual(self._answers(self.howmany).count(), 0)
        alb = self._answers(self.albino).get()
        self.assertEqual(alb.selected_choices, [0])

    def test_visible_dependent_answer_is_stored(self):
        """
        GIVEN HOW is shown only when ALB = Yes
        WHEN the POST answers ALB = Yes with a HOW value
        THEN the HOW answer is stored
        """
        self.client.get('/surveys/condvis/pick/')
        self.client.post('/surveys/condvis/pick/', {'ZONE': '1', 'ALB': '1', 'HOW': 'two'})
        self.assertEqual(self._answers(self.howmany).count(), 1)

    def test_forward_navigation_skips_hidden_sections(self):
        """
        GIVEN zone sections conditioned on ZONE
        WHEN a respondent picks zone 2 and submits
        THEN the redirect goes to area2, past the hidden area1
        """
        self.client.get('/surveys/condvis/pick/')
        response = self.client.post('/surveys/condvis/pick/', {'ZONE': '2', 'ALB': '0'})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.endswith('/area2'), response.url)

    def test_uncovered_option_flows_past_the_fan(self):
        """
        GIVEN zone 3 shows no zone section
        WHEN a respondent picks zone 3 and submits
        THEN the redirect goes straight to the final section
        """
        self.client.get('/surveys/condvis/pick/')
        response = self.client.post('/surveys/condvis/pick/', {'ZONE': '3', 'ALB': '0'})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.endswith('/final'), response.url)

    def test_changing_zone_purges_abandoned_branch(self):
        """
        GIVEN answers collected inside area1 under ZONE = 1
        WHEN the respondent re-submits the pick section with ZONE = 2
        THEN area1's stored answers are deleted
        """
        self.client.get('/surveys/condvis/pick/')
        self.client.post('/surveys/condvis/pick/', {'ZONE': '1', 'ALB': '0'})
        self.client.post('/surveys/condvis/area1/', {'A1N': 'lots of squirrels'})
        self.assertEqual(self._answers(self.a1_notes).count(), 1)
        self.client.post('/surveys/condvis/pick/', {'ZONE': '2', 'ALB': '0'})
        self.assertEqual(self._answers(self.a1_notes).count(), 0)

    def test_back_navigation_skips_hidden_sections(self):
        """
        GIVEN a respondent on the final section with ZONE = 2
        WHEN they navigate back
        THEN they land on area2, not area1
        """
        self.client.get('/surveys/condvis/pick/')
        self.client.post('/surveys/condvis/pick/', {'ZONE': '2', 'ALB': '0'})
        response = self.client.post('/surveys/condvis/final/',
                                    {'FIN': 'x', 'nav_direction': 'back'})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.endswith('/area2'), response.url)

    def test_direct_url_to_hidden_section_redirects(self):
        """
        GIVEN ZONE = 2 hides area1
        WHEN the respondent opens area1 by direct URL
        THEN they are redirected to the survey entry, not shown the section
        """
        self.client.get('/surveys/condvis/pick/')
        self.client.post('/surveys/condvis/pick/', {'ZONE': '2', 'ALB': '0'})
        response = self.client.get('/surveys/condvis/area1/')
        self.assertEqual(response.status_code, 302)

    def test_progress_counts_visible_chain(self):
        """
        GIVEN ZONE = 2 hides area1 (4 sections, 3 visible)
        WHEN the respondent renders area2
        THEN progress is 2 / 3
        """
        self.client.get('/surveys/condvis/pick/')
        self.client.post('/surveys/condvis/pick/', {'ZONE': '2', 'ALB': '0'})
        response = self.client.get('/surveys/condvis/area2/')
        self.assertEqual(response.context['section_current'], 2)
        self.assertEqual(response.context['section_total'], 3)

    def test_hidden_required_question_does_not_block_completion(self):
        """
        GIVEN required HOW hidden by ALB = No
        WHEN the respondent submits every visible section
        THEN the flow reaches the finish without a HOW answer
        """
        self.client.get('/surveys/condvis/pick/')
        self.client.post('/surveys/condvis/pick/', {'ZONE': '3', 'ALB': '0'})
        response = self.client.post('/surveys/condvis/final/', {'FIN': 'clear'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self._answers(self.howmany).count(), 0)

    def test_kill_switch_restores_full_chain(self):
        """
        GIVEN CONDITIONAL_VISIBILITY off
        WHEN a respondent picks zone 2 and submits
        THEN navigation is the raw linked list (area1 next) and nothing is purged
        """
        with self.settings(CONDITIONAL_VISIBILITY=False):
            self.client.get('/surveys/condvis/pick/')
            response = self.client.post('/surveys/condvis/pick/',
                                        {'ZONE': '2', 'ALB': '0', 'HOW': 'kept'})
            self.assertTrue(response.url.endswith('/area1'), response.url)
            self.assertEqual(self._answers(self.howmany).count(), 1)

    def test_same_section_dependent_stays_in_dom_with_rules_json(self):
        """
        GIVEN HOW conditioned on same-section ALB
        WHEN the pick section renders with no answers yet
        THEN HOW is present in the form and the rules JSON carries its rule
        """
        response = self.client.get('/surveys/condvis/pick/')
        html = response.content.decode()
        self.assertIn('name="HOW"', html)
        import json as _json
        rules = _json.loads(response.context['visibility_rules_json'])
        self.assertEqual(rules['HOW']['question_code'], 'ALB')

    def test_cross_section_hidden_question_excluded_from_form(self):
        """
        GIVEN a question in final conditioned on ZONE (earlier section) = 1
        WHEN ZONE = 2 and final renders
        THEN the conditioned question is not in the form at all
        """
        dep = Question.objects.create(
            survey_section=self.s_final, code="XDEP", order_number=2, name="Only zone 1",
            input_type="text_line",
            visibility_rule={"question_code": "ZONE", "choice_codes": [1]},
        )
        self.client.get('/surveys/condvis/pick/')
        self.client.post('/surveys/condvis/pick/', {'ZONE': '2', 'ALB': '0'})
        response = self.client.get('/surveys/condvis/final/')
        html = response.content.decode()
        self.assertNotIn('name="XDEP"', html)
        self.assertIn('name="FIN"', html)


class ConditionalVisibilityEditorTest(TestCase):
    """Editor side: Visibility block save/load, picker constraints, duplication,
    badges and lint (openspec: conditional-question-visibility)."""

    def setUp(self):
        self.org = _make_org("CondVisEd")
        self.user = User.objects.create_user(username="cv_owner", password="pass")
        Membership.objects.create(user=self.user, organization=self.org, role="owner")
        self.survey = SurveyHeader.objects.create(
            name="cv_editor", organization=self.org, status="draft",
        )
        self.s1 = SurveySection.objects.create(
            name="s1", title="Intro", survey_header=self.survey, is_head=True, code="S1")
        self.s2 = SurveySection.objects.create(
            name="s2", title="Branch", survey_header=self.survey, code="S2",
            prev_section=self.s1)
        self.s1.next_section = self.s2
        self.s1.save()
        self.ctrl = Question.objects.create(
            survey_section=self.s1, code="CTRL", order_number=1, name="Controller",
            input_type="choice",
            choices=[{"code": 1, "name": "Yes"}, {"code": 2, "name": "No"}])
        self.dep = Question.objects.create(
            survey_section=self.s1, code="DEP", order_number=2, name="Dependent",
            input_type="text_line")
        self.client.login(username="cv_owner", password="pass")

    def _edit_question(self, question, extra, htmx=False):
        payload = {
            'name': question.name, 'input_type': question.input_type,
            'subtext': '', 'color': '#000000', 'icon_class': '',
        }
        payload.update(extra)
        return self.client.post(
            f'/editor/surveys/{self.survey.uuid}/questions/{question.id}/edit/', payload,
            **({'HTTP_HX_REQUEST': 'true'} if htmx else {}))

    def test_rule_saved_via_question_edit(self):
        """
        GIVEN the Visibility block posted in conditional mode
        WHEN the question edit POST is processed
        THEN the rule lands on Question.visibility_rule
        """
        r = self._edit_question(self.dep, {
            'visibility_mode': 'conditional',
            'visibility_question': 'CTRL',
            'visibility_choices': ['1'],
        })
        self.assertEqual(r.status_code, 200)
        self.dep.refresh_from_db()
        self.assertEqual(self.dep.visibility_rule,
                         {'question_code': 'CTRL', 'choice_codes': [1]})

    def test_always_mode_clears_rule(self):
        """
        GIVEN a question with a stored rule
        WHEN the block posts mode=always
        THEN the rule is cleared
        """
        self.dep.visibility_rule = {'question_code': 'CTRL', 'choice_codes': [1]}
        self.dep.save()
        self._edit_question(self.dep, {'visibility_mode': 'always'})
        self.dep.refresh_from_db()
        self.assertIsNone(self.dep.visibility_rule)

    def test_conditional_without_choices_is_422_on_autosave(self):
        """
        GIVEN an autosave POST with conditional mode but no options ticked
        WHEN it is processed
        THEN the save returns 422 and the stored rule is untouched
        """
        r = self._edit_question(self.dep, {
            'visibility_mode': 'conditional',
            'visibility_question': 'CTRL',
            'autosave': '1',
        })
        self.assertEqual(r.status_code, 422)
        self.dep.refresh_from_db()
        self.assertIsNone(self.dep.visibility_rule)

    def test_create_conditional_without_choices_retargets_modal(self):
        """
        GIVEN the New question form posted over HTMX in conditional mode with no
              answer ticked (its hx-target is the question list, beforeend)
        WHEN the create POST is processed
        THEN the modal re-renders with the error and HX-Retarget/HX-Reswap point
             the swap at the modal body, and no question is created
        """
        before = Question.objects.count()
        r = self.client.post(
            f'/editor/surveys/{self.survey.uuid}/sections/{self.s1.id}/questions/new/',
            {'name': 'Q', 'input_type': 'text_line', 'subtext': '', 'color': '#000000',
             'icon_class': '', 'visibility_mode': 'conditional',
             'visibility_question': 'CTRL'},
            HTTP_HX_REQUEST='true')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['HX-Retarget'], '#questionModalBody')
        self.assertEqual(r['HX-Reswap'], 'innerHTML')
        self.assertContains(r, 'Pick a controlling question')
        self.assertEqual(Question.objects.count(), before)

    def test_edit_form_invalid_retargets_modal(self):
        """
        GIVEN a non-autosave edit POST in conditional mode with no answer ticked
        WHEN it is processed over HTMX
        THEN the modal is re-rendered into the modal body, not over the list item
        """
        r = self._edit_question(self.dep, {
            'visibility_mode': 'conditional', 'visibility_question': 'CTRL',
        }, htmx=True)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['HX-Retarget'], '#questionModalBody')

    def test_visibility_block_is_class_addressed(self):
        """
        GIVEN the section panel and the question modal both render the block
        WHEN either is rendered
        THEN neither carries id="fg-visibility" (the script binds by class, per
             instance — a shared id left the modal's radios dead)
        """
        for url in (
            f'/editor/surveys/{self.survey.uuid}/sections/{self.s1.id}/',
            f'/editor/surveys/{self.survey.uuid}/questions/{self.dep.id}/edit/',
        ):
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200, url)
            self.assertContains(r, 'class="form-group fg-visibility"')
            self.assertNotContains(r, 'id="fg-visibility"')

    def test_absent_block_leaves_rule_untouched(self):
        """
        GIVEN a stored rule and a POST without visibility_mode (stale form)
        WHEN the edit is processed
        THEN the rule survives
        """
        self.dep.visibility_rule = {'question_code': 'CTRL', 'choice_codes': [1]}
        self.dep.save()
        self._edit_question(self.dep, {})
        self.dep.refresh_from_db()
        self.assertIsNotNone(self.dep.visibility_rule)

    def test_section_rule_saved_via_section_detail(self):
        """
        GIVEN the block posted on the section detail form
        WHEN the section POST is processed
        THEN the rule lands on SurveySection.visibility_rule
        """
        r = self.client.post(
            f'/editor/surveys/{self.survey.uuid}/sections/{self.s2.id}/', {
                'name': self.s2.name, 'title': self.s2.title, 'code': self.s2.code,
                'subheading': '', 'layout': 'map', 'next_label': '',
                'visibility_mode': 'conditional',
                'visibility_question': 'CTRL',
                'visibility_choices': ['2'],
            })
        self.assertIn(r.status_code, (204, 302))
        self.s2.refresh_from_db()
        self.assertEqual(self.s2.visibility_rule,
                         {'question_code': 'CTRL', 'choice_codes': [2]})

    def test_modal_picker_excludes_later_and_nonchoice(self):
        """
        GIVEN a controller before and a text question after the edited question
        WHEN the edit modal renders
        THEN the picker offers only the earlier choice question
        """
        Question.objects.create(
            survey_section=self.s1, code="LATERQ", order_number=5, name="Later choice",
            input_type="choice", choices=[{"code": 1, "name": "x"}])
        r = self.client.get(
            f'/editor/surveys/{self.survey.uuid}/questions/{self.dep.id}/edit/')
        html = r.content.decode()
        self.assertIn('value="CTRL"', html)
        self.assertNotIn('value="LATERQ"', html)
        self.assertNotIn('value="DEP"', html)

    def test_duplicate_question_carries_rule(self):
        """
        GIVEN a conditioned question
        WHEN it is duplicated in the editor
        THEN the copy carries the same rule
        """
        self.dep.visibility_rule = {'question_code': 'CTRL', 'choice_codes': [1]}
        self.dep.save()
        self.client.post(
            f'/editor/surveys/{self.survey.uuid}/questions/{self.dep.id}/duplicate/')
        copy = Question.objects.filter(name__endswith='(copy)').first()
        self.assertIsNotNone(copy)
        self.assertEqual(copy.visibility_rule, self.dep.visibility_rule)

    def test_duplicate_section_remaps_intra_section_rule(self):
        """
        GIVEN a section whose question depends on a same-section controller
        WHEN the section is duplicated
        THEN the copy's rule points at the copied controller, not the source
        """
        self.dep.visibility_rule = {'question_code': 'CTRL', 'choice_codes': [1]}
        self.dep.save()
        self.client.post(
            f'/editor/surveys/{self.survey.uuid}/sections/{self.s1.id}/duplicate/')
        new_section = SurveySection.objects.filter(
            survey_header=self.survey, title__endswith='(copy)').first()
        self.assertIsNotNone(new_section)
        new_ctrl = Question.objects.get(survey_section=new_section, name="Controller")
        new_dep = Question.objects.get(survey_section=new_section, name="Dependent")
        self.assertEqual(new_dep.visibility_rule['question_code'], new_ctrl.code)
        self.assertNotEqual(new_ctrl.code, 'CTRL')

    def test_cross_survey_paste_drops_rule(self):
        """
        GIVEN a conditioned question copied to another survey
        WHEN clone_question targets the other survey's section
        THEN the pasted question has no rule
        """
        from survey.cloning import clone_question
        other = SurveyHeader.objects.create(
            name="cv_other", organization=self.org, status="draft")
        other_section = SurveySection.objects.create(
            name="os1", survey_header=other, is_head=True, code="OS1")
        self.dep.visibility_rule = {'question_code': 'CTRL', 'choice_codes': [1]}
        self.dep.save()
        clone = clone_question(self.dep, target_section=other_section)
        self.assertIsNone(clone.visibility_rule)

    def test_broken_badge_and_condition_badge_render(self):
        """
        GIVEN one valid rule and one rule referencing a removed option
        WHEN the survey structure page renders
        THEN the condition badge and the broken badge both appear
        """
        self.dep.visibility_rule = {'question_code': 'CTRL', 'choice_codes': [1]}
        self.dep.save()
        Question.objects.create(
            survey_section=self.s1, code="BRK", order_number=3, name="Broken dep",
            input_type="text_line",
            visibility_rule={'question_code': 'CTRL', 'choice_codes': [99]})
        r = self.client.get(
            f'/editor/surveys/{self.survey.uuid}/sections/{self.s1.id}/')
        html = r.content.decode()
        self.assertIn('broken rule', html)
        self.assertIn('if Controller = Yes', html)

    def test_uncovered_option_lint_renders(self):
        """
        GIVEN a section rule covering only option 1 of a 2-option controller
        WHEN the structure page renders
        THEN the lint hint names the uncovered option
        """
        self.s2.visibility_rule = {'question_code': 'CTRL', 'choice_codes': [1]}
        self.s2.save()
        r = self.client.get(f'/editor/surveys/{self.survey.uuid}/')
        self.assertIn('does not show any section', r.content.decode())

    def test_kill_switch_hides_block(self):
        """
        GIVEN CONDITIONAL_VISIBILITY off
        WHEN the question modal renders
        THEN the Visibility block is absent and rules are not saved
        """
        with self.settings(CONDITIONAL_VISIBILITY=False):
            r = self.client.get(
                f'/editor/surveys/{self.survey.uuid}/questions/{self.dep.id}/edit/')
            self.assertNotIn('visibility_mode', r.content.decode())
            self._edit_question(self.dep, {
                'visibility_mode': 'conditional',
                'visibility_question': 'CTRL',
                'visibility_choices': ['1'],
            })
            self.dep.refresh_from_db()
            self.assertIsNone(self.dep.visibility_rule)


class ConditionalVisibilitySerializationTest(TestCase):
    """ZIP round-trip of visibility rules (openspec: conditional-question-visibility)."""

    def _export_import(self, survey):
        import io
        buf = io.BytesIO()
        export_survey_to_zip(survey, buf, mode='structure')
        buf.seek(0)
        new_survey, warnings = import_survey_from_zip(buf, mode='structure')
        return {'survey': new_survey, 'warnings': warnings}

    def setUp(self):
        self.org = Organization.objects.create(name="CondVis Ser")
        self.survey = SurveyHeader.objects.create(
            name="cv_ser", organization=self.org, redirect_url="#")
        self.s1 = SurveySection.objects.create(
            survey_header=self.survey, name="pick", code="P1", is_head=True)
        self.ctrl = Question.objects.create(
            survey_section=self.s1, code="SER_CTRL", order_number=1, name="Zone",
            input_type="choice",
            choices=[{"code": 1, "name": "Area 1"}, {"code": 2, "name": "Area 2"}])
        self.s2 = SurveySection.objects.create(
            survey_header=self.survey, name="area1", code="A1",
            prev_section=self.s1,
            visibility_rule={"question_code": "SER_CTRL", "choice_codes": [1]})
        self.s1.next_section = self.s2
        self.s1.save()
        self.dep = Question.objects.create(
            survey_section=self.s1, code="SER_DEP", order_number=2, name="Dep",
            input_type="text_line",
            visibility_rule={"question_code": "SER_CTRL", "choice_codes": [2]})

    def test_round_trip_preserves_rules(self):
        """
        GIVEN a survey with a section rule and a question rule
        WHEN it is exported and imported (codes collide, so they are remapped)
        THEN both rules point at the remapped controller with the same codes
        """
        result = self._export_import(self.survey)
        new_survey = result['survey']
        new_ctrl = Question.objects.get(
            survey_section__survey_header=new_survey, name="Zone")
        new_dep = Question.objects.get(
            survey_section__survey_header=new_survey, name="Dep")
        new_s2 = SurveySection.objects.get(survey_header=new_survey, name="area1")
        self.assertEqual(new_dep.visibility_rule,
                         {"question_code": new_ctrl.code, "choice_codes": [2]})
        self.assertEqual(new_s2.visibility_rule,
                         {"question_code": new_ctrl.code, "choice_codes": [1]})
        self.assertNotEqual(new_ctrl.code, "SER_CTRL")

    def test_unresolvable_rule_dropped_with_report(self):
        """
        GIVEN an archive whose rule references a question absent from it
        WHEN the archive is imported
        THEN the item imports without a rule and a warning names the drop
        """
        self.dep.visibility_rule = {"question_code": "NO_SUCH", "choice_codes": [1]}
        self.dep.save()
        result = self._export_import(self.survey)
        new_dep = Question.objects.get(
            survey_section__survey_header=result['survey'], name="Dep")
        self.assertIsNone(new_dep.visibility_rule)
        self.assertTrue(any('visibility rule' in w for w in result.get('warnings', [])),
                        result.get('warnings'))

    def test_legacy_archive_imports_unchanged(self):
        """
        GIVEN an archive produced before visibility rules existed
        WHEN it is imported
        THEN every question and section has no rule
        """
        import io, json as _json, zipfile as _zipfile
        buf = io.BytesIO()
        export_survey_to_zip(self.survey, buf, mode='structure')
        buf.seek(0)
        with _zipfile.ZipFile(buf) as zf:
            data = _json.loads(zf.read('survey.json'))
        def strip(obj):
            if isinstance(obj, dict):
                obj.pop('visibility_rule', None)
                for v in obj.values(): strip(v)
            elif isinstance(obj, list):
                for v in obj: strip(v)
        strip(data)
        out = io.BytesIO()
        with _zipfile.ZipFile(out, 'w') as zf:
            zf.writestr('survey.json', _json.dumps(data))
        out.seek(0)
        new_survey, _warnings = import_survey_from_zip(out, mode='structure')
        self.assertFalse(Question.objects.filter(
            survey_section__survey_header=new_survey,
            visibility_rule__isnull=False).exists())
        self.assertFalse(SurveySection.objects.filter(
            survey_header=new_survey, visibility_rule__isnull=False).exists())


class PopupVisibilityEngineTest(TestCase):
    """survey/visibility.py::popup_visibility — the per-feature pop-up verdict."""

    def setUp(self):
        from survey.visibility import popup_visibility
        self.compute = popup_visibility
        self.org = Organization.objects.create(name="PopVis Org")
        self.survey = SurveyHeader.objects.create(name="popvis", organization=self.org, redirect_url="#")
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name="s1", title="S1", code="S1", is_head=True)
        self.f = _popup_fixture(self.survey, self.section)

    def test_rule_less_subquestion_always_visible(self):
        """
        GIVEN a sub-question without a rule
        WHEN the pop-up verdict is computed with no answers
        THEN it is visible
        """
        v = self.compute(self.f['point'], {}, enabled=True)
        self.assertTrue(v.is_question_visible(self.f['comment'].id))
        self.assertTrue(v.is_question_visible(self.f['kind'].id))

    def test_one_follow_up_per_pick_and_none_before(self):
        """
        GIVEN follow-ups ruled on Park and on School
        WHEN the feature's "Type of place" is School, Park, or unanswered
        THEN exactly the matching follow-up is visible, and none before the pick
        """
        v = self.compute(self.f['point'], {self.f['kind'].code: [2]}, enabled=True)
        self.assertFalse(v.is_question_visible(self.f['park'].id))
        self.assertTrue(v.is_question_visible(self.f['school'].id))
        v = self.compute(self.f['point'], {self.f['kind'].code: [1]}, enabled=True)
        self.assertTrue(v.is_question_visible(self.f['park'].id))
        self.assertFalse(v.is_question_visible(self.f['school'].id))
        v = self.compute(self.f['point'], {}, enabled=True)
        self.assertFalse(v.is_question_visible(self.f['park'].id))
        self.assertFalse(v.is_question_visible(self.f['school'].id))

    def test_cascade_through_hidden_sibling(self):
        """
        GIVEN a choice follow-up shown for Park, and a third sub-question ruled on it
        WHEN the feature is a School
        THEN the third sub-question is hidden even if its own controller value matches
        """
        self.f['park'].input_type = 'choice'
        self.f['park'].choices = [{"code": 1, "name": "Playground"}, {"code": 2, "name": "Lake"}]
        self.f['park'].save()
        third = Question.objects.create(
            survey_section=self.section, code="PV_THIRD", order_number=5, name="Third",
            input_type="text_line", parent_question_id=self.f['point'],
            visibility_rule={"question_code": "PV_PARK", "choice_codes": [1]})
        v = self.compute(self.f['point'], {"PV_KIND": [2], "PV_PARK": [1]}, enabled=True)
        self.assertFalse(v.is_question_visible(third.id))
        v = self.compute(self.f['point'], {"PV_KIND": [1], "PV_PARK": [1]}, enabled=True)
        self.assertTrue(v.is_question_visible(third.id))

    def test_broken_rules_fail_open_and_are_reported(self):
        """
        GIVEN rules whose controller is a section question, a later sibling, a non-choice
              sibling, or whose every option is gone
        WHEN the pop-up verdict is computed
        THEN each is visible and listed in `broken` with a reason
        """
        Question.objects.create(
            survey_section=self.section, code="PV_SEC", order_number=2, name="Section choice",
            input_type="choice", choices=[{"code": 1, "name": "A"}])
        cases = {
            'school': {"question_code": "PV_SEC", "choice_codes": [1]},      # not a sibling
            'kind': {"question_code": "PV_PARK", "choice_codes": [1]},       # comes later
            'comment': {"question_code": "PV_SCHOOL", "choice_codes": [1]},  # not a choice
            'park': {"question_code": "PV_KIND", "choice_codes": [99]},      # option gone
        }
        for key, rule in cases.items():
            self.f[key].visibility_rule = rule
            self.f[key].save()
        v = self.compute(self.f['point'], {}, enabled=True)
        for key in cases:
            self.assertTrue(v.is_question_visible(self.f[key].id), key)
            self.assertIn(('subquestion', self.f[key].id), v.broken, key)

    def test_kill_switch_shows_everything(self):
        """
        GIVEN valid rules
        WHEN the engine runs with enabled=False
        THEN every sub-question is visible and nothing is broken
        """
        v = self.compute(self.f['point'], {}, enabled=False)
        self.assertTrue(all(v.question_visible.values()))
        self.assertEqual(v.broken, {})

    def test_client_rules_skip_broken(self):
        """
        GIVEN one valid and one broken pop-up rule
        WHEN the client rule map is built
        THEN only the valid one is in it, keyed by sub-question code
        """
        from survey.visibility import popup_rules_for_client
        self.f['school'].visibility_rule = {"question_code": "NOPE", "choice_codes": [1]}
        self.f['school'].save()
        rules = popup_rules_for_client(self.f['point'], enabled=True)
        self.assertEqual(rules, {"PV_PARK": {"question_code": "PV_KIND", "choice_codes": [1]}})

    def test_describe_rule_and_lint_for_subquestions(self):
        """
        GIVEN a valid pop-up rule and a broken one
        WHEN describe_rule and lint_rules run
        THEN the badge label names the sibling and lint lists the broken one
        """
        from survey.visibility import describe_rule, lint_rules
        info = describe_rule('subquestion', self.f['park'], self.survey)
        self.assertEqual(info['label'], 'if Type of place = Park')
        self.f['school'].visibility_rule = {"question_code": "NOPE", "choice_codes": [1]}
        self.f['school'].save()
        self.assertTrue(describe_rule('subquestion', self.f['school'], self.survey)['broken'])
        self.assertIn(('subquestion', self.f['school'].id), lint_rules(self.survey)['broken'])

    def test_controller_options_are_earlier_choice_siblings(self):
        """
        GIVEN a pop-up with a choice first and text follow-ups after it
        WHEN controller options are listed for the School follow-up and for a new sub-question
        THEN only "Type of place" is offered
        """
        from survey.visibility import popup_controller_options
        self.assertEqual(popup_controller_options(self.f['point'], host=self.f['school']), [self.f['kind']])
        self.assertEqual(popup_controller_options(self.f['point']), [self.f['kind']])
        self.assertEqual(popup_controller_options(self.f['point'], host=self.f['kind']), [])


class PopupVisibilityRespondentTest(TestCase):
    """Server-side contract per feature and per object; what the page ships."""

    def setUp(self):
        self.org = Organization.objects.create(name="PopVis R")
        self.survey = SurveyHeader.objects.create(
            name="popvis_r", organization=self.org, status='published',
            available_languages=[], redirect_url="#")
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name="s1", title="S1", code="S1", is_head=True)
        self.f = _popup_fixture(self.survey, self.section)
        self.url = f'/surveys/{self.survey.uuid}/s1/'

    def _feature(self, x, y, props):
        return json.dumps({"type": "Feature", "geometry": {"type": "Point", "coordinates": [x, y]},
                           "properties": {"question_id": "PV_PT", **props}})

    def _post(self, features):
        self.client.get(self.url)
        return self.client.post(self.url, {'PV_PT': '|'.join(features) + '|'})

    def _child_rows(self):
        sid = self.client.session['survey_session_id']
        return Answer.objects.filter(survey_session_id=sid, parent_answer_id__isnull=False)

    def test_page_ships_popup_rules_and_every_subquestion(self):
        """
        GIVEN a point question with ruled follow-ups
        WHEN the respondent opens the section
        THEN the pop-up form still contains every sub-question and the data attribute
             carries the two rules keyed by sub-question code
        """
        html = self.client.get(self.url).content.decode()
        m = re.search(r'data-popup-visibility-rules="([^"]*)"', html)
        self.assertIsNotNone(m)
        rules = json.loads(m.group(1).replace('&quot;', '"'))
        self.assertEqual(rules, {
            "PV_PARK": {"question_code": "PV_KIND", "choice_codes": [1]},
            "PV_SCHOOL": {"question_code": "PV_KIND", "choice_codes": [2]},
        })
        forms = json.loads(re.search(r'id="sq-forms-data"[^>]*>(.*?)</script>', html, re.S).group(1))
        for code in ("PV_KIND", "PV_PARK", "PV_SCHOOL", "PV_NOTE"):
            self.assertIn(code, forms["PV_PT"])

    def test_tampered_answer_to_hidden_follow_up_is_discarded(self):
        """
        GIVEN a feature whose properties say Park but also carry a School follow-up value
        WHEN the section is submitted
        THEN the Park follow-up and the comment are stored, the School one is not
        """
        r = self._post([self._feature(13.4, 52.5, {
            "PV_KIND": ["1"], "PV_PARK": ["swings"], "PV_SCHOOL": ["tampered"], "PV_NOTE": ["ok"]})])
        self.assertIn(r.status_code, (200, 302))
        stored = {a.question.code: a.text for a in self._child_rows()}
        self.assertEqual(stored, {"PV_KIND": None, "PV_PARK": "swings", "PV_NOTE": "ok"})

    def test_two_features_decide_independently(self):
        """
        GIVEN one feature picked Park and another School, each with both follow-ups filled
        WHEN the section is submitted
        THEN the first stores the Park follow-up only and the second the School one only
        """
        self._post([
            self._feature(13.4, 52.5, {"PV_KIND": ["1"], "PV_PARK": ["p"], "PV_SCHOOL": ["x"]}),
            self._feature(13.5, 52.6, {"PV_KIND": ["2"], "PV_PARK": ["x"], "PV_SCHOOL": ["s"]}),
        ])
        by_parent = {}
        for a in self._child_rows().select_related('question', 'parent_answer_id'):
            by_parent.setdefault(a.parent_answer_id.point.x, set()).add((a.question.code, a.text))
        self.assertEqual(by_parent[13.4], {("PV_KIND", None), ("PV_PARK", "p")})
        self.assertEqual(by_parent[13.5], {("PV_KIND", None), ("PV_SCHOOL", "s")})

    def test_unanswered_controller_hides_both_follow_ups(self):
        """
        GIVEN a feature with no "Type of place" value but both follow-ups filled
        WHEN the section is submitted
        THEN neither follow-up is stored (nothing shown before the pick)
        """
        self._post([self._feature(13.4, 52.5, {"PV_PARK": ["p"], "PV_SCHOOL": ["s"], "PV_NOTE": ["n"]})])
        self.assertEqual({a.question.code for a in self._child_rows()}, {"PV_NOTE"})

    @override_settings(CONDITIONAL_VISIBILITY=False)
    def test_kill_switch_stores_everything_and_ships_no_rules(self):
        """
        GIVEN the kill switch off
        WHEN the page renders and a Park feature with both follow-ups is submitted
        THEN no rules are shipped and every sub-answer is stored
        """
        html = self.client.get(self.url).content.decode()
        self.assertIn('data-popup-visibility-rules="{}"', html)
        self._post([self._feature(13.4, 52.5, {"PV_KIND": ["1"], "PV_PARK": ["p"], "PV_SCHOOL": ["s"]})])
        self.assertEqual({a.question.code for a in self._child_rows()}, {"PV_KIND", "PV_PARK", "PV_SCHOOL"})

    def test_object_answers_follow_the_same_rule(self):
        """
        GIVEN an Objects-on-the-map question whose pop-up has a choice controller
              ("Keep" / "Remove") and a comment shown only for "Keep"
        WHEN obj__ fields post Keep + comment for object 1 and Remove + comment for object 2
        THEN object 1 keeps its comment and object 2 does not
        """
        layer = _objects_layer(self.survey, name="Sites", key_field='zone_id', label_field='name')
        q = Question.objects.create(
            survey_section=self.section, code="LO_Q", name="Objects", input_type="layer_objects",
            layer=layer, order_number=2)
        Question.objects.create(
            survey_section=self.section, code="LO_T", name="Keep it?", input_type="choice",
            parent_question_id=q, order_number=1,
            choices=[{"code": 1, "name": "Keep"}, {"code": 0, "name": "Remove"}])
        Question.objects.create(
            survey_section=self.section, code="LO_C", name="Why?", input_type="text",
            parent_question_id=q, order_number=2,
            visibility_rule={"question_code": "LO_T", "choice_codes": [1]})
        self.client.get(self.url)
        self.client.post(self.url, {
            'obj__1__LO_T': '1', 'obj__1__LO_C': 'yes please',
            'obj__2__LO_T': '0', 'obj__2__LO_C': 'should be dropped',
        })
        sid = self.client.session['survey_session_id']
        rows = Answer.objects.filter(survey_session_id=sid, layer_object__isnull=False).select_related('question', 'layer_object')
        got = {(a.layer_object.key, a.question.code): a.text for a in rows}
        self.assertEqual(got, {('1', 'LO_T'): None, ('1', 'LO_C'): 'yes please', ('2', 'LO_T'): None})

    def test_export_unchanged_for_rule_less_subquestions(self):
        """
        GIVEN a submitted Park feature
        WHEN the data export bundle is collected
        THEN the observations table has one column per sub-question, hidden or not,
             and the hidden follow-up's cell is simply empty
        """
        from survey import export
        self._post([self._feature(13.4, 52.5, {"PV_KIND": ["1"], "PV_PARK": ["p"], "PV_NOTE": ["n"]})])
        bundle = export.collect(self.survey, [(self.survey, '')])
        layer = [g for g in bundle.parts[0].geo_layers if g.question.code == 'PV_PT'][0]
        self.assertEqual(layer.sub_columns, ['Type of place', 'Park follow-up', 'School follow-up', 'Comment'])
        props = layer.collection['features'][0]['properties']
        self.assertEqual(props['Park follow-up'], 'p')
        self.assertEqual(props['School follow-up'], '')


class PopupVisibilityEditorTest(TestCase):
    """Visibility block in the sub-question modal, badges, pill, live-survey refusal."""

    def setUp(self):
        self.org = _make_org("PopVisEd")
        self.user = User.objects.create_user(username="pv_owner", password="pass")
        Membership.objects.create(user=self.user, organization=self.org, role="owner")
        self.survey = SurveyHeader.objects.create(
            name="pv_editor", organization=self.org, status="draft")
        self.section = SurveySection.objects.create(
            name="s1", title="Intro", survey_header=self.survey, is_head=True, code="S1")
        Question.objects.create(
            survey_section=self.section, code="SEC_CHOICE", order_number=0, name="Section choice",
            input_type="choice", choices=[{"code": 1, "name": "A"}])
        self.f = _popup_fixture(self.survey, self.section, with_rules=False)
        self.client.login(username="pv_owner", password="pass")

    def _edit(self, question, extra):
        payload = {'name': question.name, 'input_type': question.input_type,
                   'subtext': '', 'color': '#000000', 'icon_class': ''}
        payload.update(extra)
        return self.client.post(
            f'/editor/surveys/{self.survey.uuid}/questions/{question.id}/edit/', payload)

    def test_subquestion_modal_offers_siblings_only(self):
        """
        GIVEN a pop-up with a choice first and a section-level choice question
        WHEN the School follow-up's modal and the new-sub-question modal render
        THEN the Visibility block lists "Type of place" under "This pop-up" and never the
             section question; the controller's own modal says nothing can control it yet
        """
        html = self.client.get(
            f'/editor/surveys/{self.survey.uuid}/questions/{self.f["school"].id}/edit/').content.decode()
        self.assertIn('name="visibility_mode"', html)
        self.assertIn('This pop-up', html)
        self.assertIn('value="PV_KIND"', html)
        self.assertNotIn('value="SEC_CHOICE"', html)
        html = self.client.get(
            f'/editor/surveys/{self.survey.uuid}/questions/{self.f["point"].id}/subquestions/new/').content.decode()
        self.assertIn('value="PV_KIND"', html)
        self.assertNotIn('value="SEC_CHOICE"', html)
        html = self.client.get(
            f'/editor/surveys/{self.survey.uuid}/questions/{self.f["kind"].id}/edit/').content.decode()
        self.assertIn('No earlier choice sub-question in this pop-up', html)

    def test_rule_saved_via_subquestion_edit_and_create(self):
        """
        GIVEN the Visibility block posted in conditional mode
        WHEN a sub-question is edited and another created with it
        THEN both rules land on the rows and the section-list row shows the badge
        """
        r = self._edit(self.f['park'], {
            'visibility_mode': 'conditional', 'visibility_question': 'PV_KIND',
            'visibility_choices': ['1']})
        self.assertEqual(r.status_code, 200)
        self.f['park'].refresh_from_db()
        self.assertEqual(self.f['park'].visibility_rule, {'question_code': 'PV_KIND', 'choice_codes': [1]})
        self.assertIn('if Type of place = Park', r.content.decode())
        r = self.client.post(
            f'/editor/surveys/{self.survey.uuid}/questions/{self.f["point"].id}/subquestions/new/', {
                'name': 'Shop follow-up', 'input_type': 'text_line', 'subtext': '', 'color': '#000000',
                'icon_class': '', 'visibility_mode': 'conditional', 'visibility_question': 'PV_KIND',
                'visibility_choices': ['2']})
        self.assertEqual(r.status_code, 200)
        created = Question.objects.get(name='Shop follow-up')
        self.assertEqual(created.parent_question_id_id, self.f['point'].id)
        self.assertEqual(created.visibility_rule, {'question_code': 'PV_KIND', 'choice_codes': [2]})

    def test_badges_pill_and_dependents_in_modal_and_list(self):
        """
        GIVEN two follow-ups ruled on "Type of place" and one broken rule
        WHEN the section page and the parent's modal render
        THEN rows show the branch badges, the controller shows "2", the broken one is badged,
             and the follow-up's modal carries the "Shown when" pill
        """
        for key, code in (('park', 1), ('school', 2)):
            self.f[key].visibility_rule = {'question_code': 'PV_KIND', 'choice_codes': [code]}
            self.f[key].save()
        self.f['comment'].visibility_rule = {'question_code': 'SEC_CHOICE', 'choice_codes': [1]}
        self.f['comment'].save()
        html = self.client.get(
            f'/editor/surveys/{self.survey.uuid}/sections/{self.section.id}/').content.decode()
        self.assertIn('if Type of place = Park', html)
        self.assertIn('if Type of place = School', html)
        self.assertIn('broken rule', html)
        self.assertIn('<i class="fas fa-code-branch"></i> 2</span>', html)
        modal = self.client.get(
            f'/editor/surveys/{self.survey.uuid}/questions/{self.f["point"].id}/edit/').content.decode()
        self.assertIn('if Type of place = Park', modal)
        self.assertIn('broken rule', modal)
        pill = self.client.get(
            f'/editor/surveys/{self.survey.uuid}/questions/{self.f["park"].id}/edit/').content.decode()
        self.assertIn('Shown when:', pill)

    def test_rule_change_on_live_survey_is_structural(self):
        """
        GIVEN a published survey
        WHEN a sub-question's rule is changed through the edit form
        THEN the save is refused with the unpublished-changes affordance and nothing is stored
        """
        self.survey.status = 'published'
        self.survey.save(update_fields=['status'])
        r = self._edit(self.f['park'], {
            'visibility_mode': 'conditional', 'visibility_question': 'PV_KIND',
            'visibility_choices': ['1'], 'autosave': '1'})
        self.assertEqual(r.status_code, 422)
        self.assertTrue(r.json().get('needs_unpublished_changes'))
        self.f['park'].refresh_from_db()
        self.assertIsNone(self.f['park'].visibility_rule)

    def test_section_preview_ships_popup_rules(self):
        """
        GIVEN a ruled follow-up
        WHEN the editor's section preview renders
        THEN it carries the pop-up rules and card markup for the pop-up form
        """
        self.f['park'].visibility_rule = {'question_code': 'PV_KIND', 'choice_codes': [1]}
        self.f['park'].save()
        r = self.client.get(f'/editor/surveys/{self.survey.uuid}/preview/{self.section.name}/')
        self.assertEqual(r.status_code, 200)
        html = r.content.decode()
        self.assertIn('PV_PARK', re.search(r'data-popup-visibility-rules="([^"]*)"', html).group(1))
        forms = json.loads(re.search(r'id="sq-forms-data"[^>]*>(.*?)</script>', html, re.S).group(1))
        self.assertIn('data-field-name="PV_PARK"', forms['PV_PT'])


class PopupVisibilitySerializationTest(TestCase):
    """Pop-up rules through ZIP, duplication, cross-survey paste and publish."""

    def setUp(self):
        self.org = _make_org("PopVisSer")
        self.user = User.objects.create_user(username="pv_ser", password="pass")
        Membership.objects.create(user=self.user, organization=self.org, role="owner")
        self.survey = SurveyHeader.objects.create(
            name="pv_ser", organization=self.org, redirect_url="#", status="draft")
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name="s1", title="S1", code="S1", is_head=True)
        self.f = _popup_fixture(self.survey, self.section)
        self.client.login(username="pv_ser", password="pass")

    def _export_import(self):
        import io
        buf = io.BytesIO()
        export_survey_to_zip(self.survey, buf, mode='structure')
        buf.seek(0)
        return import_survey_from_zip(buf, mode='structure')

    def test_zip_round_trip_remaps_sibling(self):
        """
        GIVEN a survey with ruled follow-ups
        WHEN it is exported and imported into the same database (codes collide)
        THEN the imported follow-ups point at the imported "Type of place" code
        """
        new_survey, warnings = self._export_import()
        new_kind = Question.objects.get(survey_section__survey_header=new_survey, name="Type of place")
        new_park = Question.objects.get(survey_section__survey_header=new_survey, name="Park follow-up")
        self.assertNotEqual(new_kind.code, "PV_KIND")
        self.assertEqual(new_park.visibility_rule, {"question_code": new_kind.code, "choice_codes": [1]})
        self.assertFalse(any('visibility rule' in w for w in warnings), warnings)

    def test_unresolvable_popup_rule_dropped_with_report(self):
        """
        GIVEN a follow-up whose rule names a code absent from the pop-up
        WHEN the archive is imported
        THEN the follow-up has no rule and a warning names the sub-question
        """
        self.f['school'].visibility_rule = {"question_code": "NO_SUCH", "choice_codes": [1]}
        self.f['school'].save()
        new_survey, warnings = self._export_import()
        new_school = Question.objects.get(survey_section__survey_header=new_survey, name="School follow-up")
        self.assertIsNone(new_school.visibility_rule)
        self.assertTrue(any("sub-question 'School follow-up'" in w for w in warnings), warnings)

    def test_duplicate_point_question_remaps_popup_rules(self):
        """
        GIVEN the point question with ruled follow-ups
        WHEN it is duplicated in the editor
        THEN the copy's follow-ups are ruled on the copy's "Type of place"
        """
        self.client.post(f'/editor/surveys/{self.survey.uuid}/questions/{self.f["point"].id}/duplicate/')
        copy = Question.objects.get(name="Place (copy)")
        new_kind = Question.objects.get(parent_question_id=copy, name="Type of place")
        new_park = Question.objects.get(parent_question_id=copy, name="Park follow-up")
        self.assertNotEqual(new_kind.code, "PV_KIND")
        self.assertEqual(new_park.visibility_rule, {"question_code": new_kind.code, "choice_codes": [1]})

    def test_cross_survey_paste_keeps_popup_rules(self):
        """
        GIVEN the point question pasted into another survey
        WHEN clone_question targets the other survey's section
        THEN the pasted follow-ups keep their rule, remapped to the pasted sibling
        """
        from survey.cloning import clone_question
        other = SurveyHeader.objects.create(name="pv_other", organization=self.org, status="draft")
        other_section = SurveySection.objects.create(name="os1", survey_header=other, is_head=True, code="OS1")
        clone = clone_question(self.f['point'], target_section=other_section)
        new_kind = Question.objects.get(parent_question_id=clone, name="Type of place")
        new_school = Question.objects.get(parent_question_id=clone, name="School follow-up")
        self.assertEqual(new_school.visibility_rule, {"question_code": new_kind.code, "choice_codes": [2]})

    def test_publish_draft_keeps_popup_rules(self):
        """
        GIVEN a published survey with ruled follow-ups and a draft copy of it
        WHEN the draft is published
        THEN the live follow-ups still carry the rules verbatim
        """
        from survey.versioning import clone_survey_for_draft, publish_draft
        self.survey.status = 'published'
        self.survey.save(update_fields=['status'])
        draft = clone_survey_for_draft(self.survey)
        publish_draft(draft)
        live_park = Question.objects.get(survey_section__survey_header=self.survey, name="Park follow-up")
        self.assertEqual(live_park.visibility_rule, {"question_code": "PV_KIND", "choice_codes": [1]})


# ─── "answered (any option)" match mode (change visibility-answered-condition, #339) ──

class AnsweredRuleEngineTest(TestCase):
    """survey/visibility.py — the answered mode through verdict, match, lint, label."""

    def setUp(self):
        from survey.visibility import compute_visibility
        self.compute = compute_visibility
        org = Organization.objects.create(name="Ans Org")
        self.survey = SurveyHeader.objects.create(name="ans_survey", organization=org, redirect_url="#")
        self.s1 = SurveySection.objects.create(
            survey_header=self.survey, name="intro", title="intro", code="S1", is_head=True)
        self.ctrl = Question.objects.create(
            survey_section=self.s1, code="CTRL", order_number=1, name="Kind",
            input_type="choice", choices=[{"code": 1, "name": "A"}, {"code": 2, "name": "B"}])

    def _section(self, name, prev, rule=None):
        section = SurveySection.objects.create(
            survey_header=self.survey, name=name, title=name, code=name[:8], visibility_rule=rule)
        prev.next_section = section
        prev.save()
        section.prev_section = prev
        section.save()
        return section

    def test_question_hidden_until_any_option_picked(self):
        """
        GIVEN a question ruled "CTRL answered"
        WHEN CTRL is unanswered, answered 1, answered 2, or answered with a code
             not among its options
        THEN the question is hidden only in the unanswered case
        """
        q = Question.objects.create(
            survey_section=self.s1, code="DEP", order_number=2, name="Dep", input_type="text_line",
            visibility_rule={"question_code": "CTRL", "answered": True})
        self.assertFalse(self.compute(self.survey, {}, enabled=True).is_question_visible(q.id))
        self.assertFalse(self.compute(self.survey, {"CTRL": []}, enabled=True).is_question_visible(q.id))
        for picked in ([1], [2], [7]):
            self.assertTrue(self.compute(self.survey, {"CTRL": picked}, enabled=True).is_question_visible(q.id), picked)

    def test_option_added_later_counts_without_rule_change(self):
        """
        GIVEN a section ruled "CTRL answered" written when CTRL had options 1, 2
        WHEN option 3 is added and a respondent picks it
        THEN the section is shown and the rule is not broken
        """
        s2 = self._section("details", self.s1, rule={"question_code": "CTRL", "answered": True})
        self.ctrl.choices = self.ctrl.choices + [{"code": 3, "name": "C"}]
        self.ctrl.save()
        vmap = self.compute(self.survey, {"CTRL": [3]}, enabled=True)
        self.assertTrue(vmap.is_section_visible(s2.id))
        self.assertEqual(vmap.broken, {})

    def test_answered_rule_survives_option_removal_but_not_controller_loss(self):
        """
        GIVEN a section ruled "CTRL answered"
        WHEN every original option of CTRL is replaced
        THEN the rule is intact; when CTRL becomes a text question or moves
             after the section, it is broken and fails open
        """
        from survey.visibility import lint_rules
        s2 = self._section("details", self.s1, rule={"question_code": "CTRL", "answered": True})
        self.ctrl.choices = [{"code": 9, "name": "Z"}]
        self.ctrl.save()
        self.assertEqual(lint_rules(self.survey)['broken'], {})
        self.assertFalse(self.compute(self.survey, {}, enabled=True).is_section_visible(s2.id))
        self.ctrl.input_type = "text_line"
        self.ctrl.save()
        vmap = self.compute(self.survey, {}, enabled=True)
        self.assertTrue(vmap.is_section_visible(s2.id))
        self.assertIn(("section", s2.id), vmap.broken)

    def test_hidden_controller_satisfies_nothing(self):
        """
        GIVEN B ruled "A answered" and A ruled "CTRL = 1"
        WHEN CTRL = 2 while an answer to A is still stored
        THEN B is hidden (cascade)
        """
        a = Question.objects.create(
            survey_section=self.s1, code="A", order_number=2, name="A", input_type="choice",
            choices=[{"code": 1, "name": "x"}],
            visibility_rule={"question_code": "CTRL", "choice_codes": [1]})
        b = Question.objects.create(
            survey_section=self.s1, code="B", order_number=3, name="B", input_type="text_line",
            visibility_rule={"question_code": "A", "answered": True})
        vmap = self.compute(self.survey, {"CTRL": [2], "A": [1]}, enabled=True)
        self.assertFalse(vmap.is_question_visible(a.id))
        self.assertFalse(vmap.is_question_visible(b.id))
        self.assertTrue(self.compute(self.survey, {"CTRL": [1], "A": [1]}, enabled=True).is_question_visible(b.id))

    def test_answered_wins_over_stray_codes(self):
        """
        GIVEN a rule carrying both answered: true and choice_codes [99]
        WHEN CTRL = 1
        THEN the answered mode applies and the item is shown
        """
        from survey.visibility import rule_mode
        rule = {"question_code": "CTRL", "answered": True, "choice_codes": [99]}
        self.assertEqual(rule_mode(rule), "answered")
        q = Question.objects.create(
            survey_section=self.s1, code="DEP", order_number=2, name="Dep", input_type="text_line",
            visibility_rule=rule)
        self.assertTrue(self.compute(self.survey, {"CTRL": [1]}, enabled=True).is_question_visible(q.id))

    def test_lint_answered_section_covers_every_option(self):
        """
        GIVEN fan sections for option 1 and one section ruled "CTRL answered"
        WHEN lint_rules runs
        THEN no option is uncovered and both count as dependents
        """
        from survey.visibility import lint_rules
        fan = self._section("fan1", self.s1, rule={"question_code": "CTRL", "choice_codes": [1]})
        self._section("rest", fan, rule={"question_code": "CTRL", "answered": True})
        report = lint_rules(self.survey)
        self.assertEqual(report['dependents'].get(self.ctrl.id), 2)
        self.assertNotIn(self.ctrl.id, report['uncovered'])

    def test_describe_and_client_shape(self):
        """
        GIVEN an answered rule on a question and on a pop-up sub-question
        WHEN describe_rule, client_rule and popup_rules_for_client run
        THEN the label reads "if Kind answered" and the client gets {"answered": true}
        """
        from survey.visibility import describe_rule, client_rule, popup_rules_for_client
        q = Question.objects.create(
            survey_section=self.s1, code="DEP", order_number=2, name="Dep", input_type="text_line",
            visibility_rule={"question_code": "CTRL", "answered": True})
        info = describe_rule('question', q, self.survey)
        self.assertEqual((info['label'], info['broken']), ('if Kind answered', False))
        self.assertEqual(client_rule(q.visibility_rule), {"question_code": "CTRL", "answered": True})
        f = _popup_fixture(self.survey, self.s1, code_prefix="AN", with_rules=False)
        f['park'].visibility_rule = {"question_code": f['kind'].code, "answered": True}
        f['park'].save()
        self.assertEqual(popup_rules_for_client(f['point'], enabled=True),
                         {f['park'].code: {"question_code": f['kind'].code, "answered": True}})
        self.assertEqual(describe_rule('subquestion', f['park'], self.survey)['label'],
                         'if Type of place answered')

    def test_popup_follow_up_shown_for_any_type(self):
        """
        GIVEN a pop-up follow-up ruled "Type of place answered"
        WHEN the feature's type is Park, School, or unanswered
        THEN the follow-up is visible for both types and hidden before the pick
        """
        from survey.visibility import popup_visibility
        f = _popup_fixture(self.survey, self.s1, code_prefix="AN", with_rules=False)
        f['park'].visibility_rule = {"question_code": f['kind'].code, "answered": True}
        f['park'].save()
        for picked in ([1], [2]):
            self.assertTrue(popup_visibility(f['point'], {f['kind'].code: picked}, enabled=True)
                            .is_question_visible(f['park'].id))
        self.assertFalse(popup_visibility(f['point'], {}, enabled=True).is_question_visible(f['park'].id))


class AnsweredRuleRespondentTest(TestCase):
    """A section ruled "answered" on the respondent side: navigation, progress,
    the client rule shape."""

    def setUp(self):
        self.client = Client()
        org = Organization.objects.create(name="AnsResp Org")
        self.survey = SurveyHeader.objects.create(
            name="ansresp", organization=org, status='published',
            available_languages=[], redirect_url="#")
        self.pick = SurveySection.objects.create(
            survey_header=self.survey, name="pick", title="Pick", code="S1", is_head=True)
        Question.objects.create(
            survey_section=self.pick, code="ZONE", order_number=1, name="Zone?",
            input_type="choice", choices=[{"code": i, "name": f"Area {i}"} for i in (1, 2)])
        Question.objects.create(
            survey_section=self.pick, code="FREE", order_number=2, name="Free",
            input_type="text_line")
        self.details = SurveySection.objects.create(
            survey_header=self.survey, name="details", title="Details", code="S2",
            visibility_rule={"question_code": "ZONE", "answered": True})
        Question.objects.create(
            survey_section=self.details, code="DET", order_number=1, name="Details",
            input_type="text_line")
        self.final = SurveySection.objects.create(
            survey_header=self.survey, name="final", title="Final", code="S3")
        Question.objects.create(
            survey_section=self.final, code="FIN", order_number=1, name="Fin",
            input_type="text_line")
        self.pick.next_section = self.details; self.pick.save()
        self.details.prev_section = self.pick; self.details.next_section = self.final; self.details.save()
        self.final.prev_section = self.details; self.final.save()

    def test_section_skipped_until_any_zone_picked(self):
        """
        GIVEN "Details" shown when ZONE is answered
        WHEN the respondent submits the first page without a zone, then with zone 2
        THEN the first submit skips to the final page and the second lands on Details
        """
        self.client.get('/surveys/ansresp/pick/')
        r = self.client.post('/surveys/ansresp/pick/', {'FREE': 'x'})
        self.assertEqual(r.status_code, 302)
        self.assertTrue(r.url.endswith('/final'), r.url)
        r = self.client.post('/surveys/ansresp/pick/', {'FREE': 'x', 'ZONE': '2'})
        self.assertEqual(r.status_code, 302)
        self.assertTrue(r.url.endswith('/details'), r.url)

    def test_progress_counts_the_section_only_when_shown(self):
        """
        GIVEN the same survey (3 sections)
        WHEN the respondent renders the final page without a zone, then with one
        THEN progress reads 2 / 2, then 3 / 3
        """
        self.client.get('/surveys/ansresp/pick/')
        self.client.post('/surveys/ansresp/pick/', {'FREE': 'x'})
        r = self.client.get('/surveys/ansresp/final/')
        self.assertEqual((r.context['section_current'], r.context['section_total']), (2, 2))
        self.client.post('/surveys/ansresp/pick/', {'FREE': 'x', 'ZONE': '1'})
        r = self.client.get('/surveys/ansresp/final/')
        self.assertEqual((r.context['section_current'], r.context['section_total']), (3, 3))

    def test_same_section_rule_reaches_client_in_answered_shape(self):
        """
        GIVEN a same-section question ruled "ZONE answered"
        WHEN the page renders
        THEN the card stays in the DOM and data-visibility-rules carries {"answered": true}
        """
        import re
        Question.objects.create(
            survey_section=self.pick, code="WHY", order_number=3, name="Why",
            input_type="text_line", visibility_rule={"question_code": "ZONE", "answered": True})
        html = self.client.get('/surveys/ansresp/pick/').content.decode()
        m = re.search(r'data-visibility-rules="([^"]*)"', html)
        self.assertIsNotNone(m)
        import html as html_module
        rules = json.loads(html_module.unescape(m.group(1)))
        self.assertEqual(rules['WHY'], {"question_code": "ZONE", "answered": True})
        self.assertIn('data-field-name="WHY"', html)


class AnsweredRuleEditorTest(TestCase):
    """The match select in the Visibility block and the stored shape."""

    def setUp(self):
        self.org = _make_org("AnsEd")
        self.user = User.objects.create_user(username="ans_owner", password="pass")
        Membership.objects.create(user=self.user, organization=self.org, role="owner")
        self.survey = SurveyHeader.objects.create(name="ans_editor", organization=self.org, status="draft")
        self.s1 = SurveySection.objects.create(
            name="s1", title="Intro", survey_header=self.survey, is_head=True, code="S1")
        self.s2 = SurveySection.objects.create(
            name="s2", title="Branch", survey_header=self.survey, code="S2", prev_section=self.s1)
        self.s1.next_section = self.s2
        self.s1.save()
        self.ctrl = Question.objects.create(
            survey_section=self.s1, code="CTRL", order_number=1, name="Controller",
            input_type="choice", choices=[{"code": 1, "name": "Yes"}, {"code": 2, "name": "No"}])
        self.dep = Question.objects.create(
            survey_section=self.s1, code="DEP", order_number=2, name="Dependent", input_type="text_line")
        self.client.login(username="ans_owner", password="pass")

    def _edit_question(self, question, extra):
        payload = {'name': question.name, 'input_type': question.input_type,
                   'subtext': '', 'color': '#000000', 'icon_class': ''}
        payload.update(extra)
        return self.client.post(
            f'/editor/surveys/{self.survey.uuid}/questions/{question.id}/edit/', payload)

    def test_answered_match_stores_shape_without_codes(self):
        """
        GIVEN the block posted with visibility_match=answered and stale ticked codes
        WHEN the question edit POST is processed
        THEN the stored rule is {"question_code", "answered": true} and nothing else
        """
        r = self._edit_question(self.dep, {
            'visibility_mode': 'conditional', 'visibility_question': 'CTRL',
            'visibility_match': 'answered', 'visibility_choices': ['1'],
        })
        self.assertEqual(r.status_code, 200)
        self.dep.refresh_from_db()
        self.assertEqual(self.dep.visibility_rule, {'question_code': 'CTRL', 'answered': True})

    def test_any_of_and_absent_match_keep_the_old_shape(self):
        """
        GIVEN the block posted with visibility_match=any_of, then without the field
        WHEN each POST is processed
        THEN both store the choice_codes shape
        """
        for extra in ({'visibility_match': 'any_of'}, {}):
            self._edit_question(self.dep, {
                'visibility_mode': 'conditional', 'visibility_question': 'CTRL',
                'visibility_choices': ['2'], **extra})
            self.dep.refresh_from_db()
            self.assertEqual(self.dep.visibility_rule, {'question_code': 'CTRL', 'choice_codes': [2]})

    def test_answered_without_controller_is_an_error(self):
        """
        GIVEN visibility_match=answered and no controlling question
        WHEN the edit POST is processed
        THEN no rule is stored and the form reports the error
        """
        self.client.post(f'/editor/surveys/{self.survey.uuid}/questions/{self.dep.id}/edit/', {
            'name': 'Dependent', 'input_type': 'text_line', 'subtext': '', 'color': '#000000',
            'icon_class': '', 'visibility_mode': 'conditional', 'visibility_match': 'answered',
            'visibility_question': ''})
        self.dep.refresh_from_db()
        self.assertIsNone(self.dep.visibility_rule)

    def test_section_rule_answered_via_section_detail(self):
        """
        GIVEN the block posted on the section form in answered mode
        WHEN the section POST is processed
        THEN the section's rule is the answered shape
        """
        r = self.client.post(f'/editor/surveys/{self.survey.uuid}/sections/{self.s2.id}/', {
            'name': self.s2.name, 'title': self.s2.title, 'code': self.s2.code,
            'subheading': '', 'layout': 'map', 'next_label': '',
            'visibility_mode': 'conditional', 'visibility_question': 'CTRL',
            'visibility_match': 'answered'})
        self.assertIn(r.status_code, (204, 302))
        self.s2.refresh_from_db()
        self.assertEqual(self.s2.visibility_rule, {'question_code': 'CTRL', 'answered': True})

    def test_block_renders_saved_mode_and_badge(self):
        """
        GIVEN a question with an answered rule
        WHEN its modal and the section list render
        THEN the match select has "answered" selected, the option list is hidden,
             and the badge reads "if Controller answered"
        """
        self.dep.visibility_rule = {'question_code': 'CTRL', 'answered': True}
        self.dep.save()
        html = self.client.get(
            f'/editor/surveys/{self.survey.uuid}/questions/{self.dep.id}/edit/').content.decode()
        self.assertIn('name="visibility_match"', html)
        self.assertRegex(html, r'value="answered"\s+selected')
        self.assertRegex(html, r'visibility-any-of"[^>]*display:none')
        self.assertIn('Shown when:', html)          # the modal pill slices off "if "
        self.assertIn('Controller answered', html)
        html = self.client.get(
            f'/editor/surveys/{self.survey.uuid}/sections/{self.s1.id}/').content.decode()
        self.assertIn('if Controller answered', html)
        self.assertNotIn('broken rule', html)

    def test_block_default_is_any_of(self):
        """
        GIVEN a question with an any-of rule
        WHEN its modal renders
        THEN "any_of" is selected and the option list is shown
        """
        self.dep.visibility_rule = {'question_code': 'CTRL', 'choice_codes': [1]}
        self.dep.save()
        html = self.client.get(
            f'/editor/surveys/{self.survey.uuid}/questions/{self.dep.id}/edit/').content.decode()
        self.assertRegex(html, r'value="any_of"\s+selected')
        self.assertNotRegex(html, r'visibility-any-of"[^>]*display:none')


class AnsweredRuleSerializationTest(TestCase):
    """Both rule shapes through ZIP export/import and duplication."""

    def setUp(self):
        self.org = Organization.objects.create(name="Ans Ser")
        self.survey = SurveyHeader.objects.create(name="ans_ser", organization=self.org, redirect_url="#")
        self.s1 = SurveySection.objects.create(survey_header=self.survey, name="pick", code="P1", is_head=True)
        self.ctrl = Question.objects.create(
            survey_section=self.s1, code="ANS_CTRL", order_number=1, name="Zone", input_type="choice",
            choices=[{"code": 1, "name": "Area 1"}, {"code": 2, "name": "Area 2"}])
        self.s2 = SurveySection.objects.create(
            survey_header=self.survey, name="details", code="D1", prev_section=self.s1,
            visibility_rule={"question_code": "ANS_CTRL", "answered": True})
        self.s1.next_section = self.s2
        self.s1.save()
        self.dep = Question.objects.create(
            survey_section=self.s1, code="ANS_DEP", order_number=2, name="Dep", input_type="text_line",
            visibility_rule={"question_code": "ANS_CTRL", "choice_codes": [2]})
        self.f = _popup_fixture(self.survey, self.s1, code_prefix="ANS", with_rules=False)
        self.f['park'].visibility_rule = {"question_code": self.f['kind'].code, "answered": True}
        self.f['park'].save()

    def _export_import(self):
        import io
        buf = io.BytesIO()
        export_survey_to_zip(self.survey, buf, mode='structure')
        buf.seek(0)
        return import_survey_from_zip(buf, mode='structure')

    def test_both_shapes_round_trip(self):
        """
        GIVEN an answered section rule, an any-of question rule and an answered pop-up rule
        WHEN the survey is exported and imported (codes collide and are remapped)
        THEN each rule keeps its mode and names the remapped controller
        """
        new_survey, warnings = self._export_import()
        new_ctrl = Question.objects.get(survey_section__survey_header=new_survey, name="Zone")
        new_dep = Question.objects.get(survey_section__survey_header=new_survey, name="Dep")
        new_s2 = SurveySection.objects.get(survey_header=new_survey, name="details")
        new_kind = Question.objects.get(survey_section__survey_header=new_survey, name="Type of place")
        new_park = Question.objects.get(survey_section__survey_header=new_survey, name="Park follow-up")
        self.assertNotEqual(new_ctrl.code, "ANS_CTRL")
        self.assertEqual(new_s2.visibility_rule, {"question_code": new_ctrl.code, "answered": True})
        self.assertEqual(new_dep.visibility_rule, {"question_code": new_ctrl.code, "choice_codes": [2]})
        self.assertEqual(new_park.visibility_rule, {"question_code": new_kind.code, "answered": True})
        self.assertFalse(any('visibility rule' in w for w in warnings), warnings)

    def test_answered_rule_imports_even_when_options_changed(self):
        """
        GIVEN an archive whose controller lost every option the any-of rule named
        WHEN it is imported
        THEN the answered rule is kept (it references no option codes), while the
             any-of rule on the same controller is dropped with a report
        """
        self.ctrl.choices = [{"code": 9, "name": "Area 9"}]
        self.ctrl.save()
        new_survey, warnings = self._export_import()
        new_s2 = SurveySection.objects.get(survey_header=new_survey, name="details")
        new_dep = Question.objects.get(survey_section__survey_header=new_survey, name="Dep")
        self.assertEqual(new_s2.visibility_rule["answered"], True)
        self.assertIsNone(new_dep.visibility_rule)
        self.assertTrue(any("question 'Dep'" in w for w in warnings), warnings)

    def test_duplicate_section_keeps_answered_rule(self):
        """
        GIVEN the answered section rule
        WHEN the section is cloned within the survey
        THEN the copy carries the same rule dict
        """
        from survey.cloning import clone_section
        copy = clone_section(self.s2, target_survey=self.survey)
        self.assertEqual(copy.visibility_rule, {"question_code": "ANS_CTRL", "answered": True})


class AudienceHiddenIsNotApplicableTest(TestCase):
    """Delta of change operator-entry: an item whose audience excludes the
    respondent surface is "hidden" for every server-side rule."""

    def setUp(self):
        self.client = Client()
        org = Organization.objects.create(name="Audience Org")
        self.survey = SurveyHeader.objects.create(
            name="audvis", organization=org, status='published',
            available_languages=[], redirect_url="#",
        )
        self.s1 = SurveySection.objects.create(
            survey_header=self.survey, name="pick", title="Pick", code="S1", is_head=True,
        )
        self.alb = Question.objects.create(
            survey_section=self.s1, code="ALB", order_number=1, name="Albino?",
            input_type="choice", choices=[{"code": 1, "name": "Yes"}, {"code": 0, "name": "No"}],
        )
        self.how = Question.objects.create(
            survey_section=self.s1, code="HOW", order_number=2, name="How many?",
            input_type="text_line",
            visibility_rule={"question_code": "ALB", "choice_codes": [1]},
        )
        self.sheet = Question.objects.create(
            survey_section=self.s1, code="SHEET", order_number=3, name="Sheet number",
            input_type="text_line", audience="operators", required=True,
        )

    def _answers(self, question):
        session = SurveySession.objects.get(pk=self.client.session['survey_session_id'])
        return Answer.objects.filter(survey_session=session, question=question)

    def test_operator_only_question_posted_by_a_respondent_is_discarded(self):
        """
        GIVEN a question with audience `operators`
        WHEN a respondent opens the section and posts a value for its code
        THEN the page never rendered it and no Answer row is stored for it
        """
        page = self.client.get('/surveys/audvis/pick/')
        self.assertNotContains(page, 'name="SHEET"')
        self.client.post('/surveys/audvis/pick/', {'ALB': '0', 'SHEET': '17'})
        self.assertEqual(self._answers(self.sheet).count(), 0)
        self.assertEqual(self._answers(self.alb).count(), 1)

    @override_settings(CONDITIONAL_VISIBILITY=False)
    def test_kill_switch_leaves_audience_on(self):
        """
        GIVEN CONDITIONAL_VISIBILITY is off
        WHEN the respondent opens the section
        THEN rule-conditioned HOW renders but the operator-only question does not
        """
        page = self.client.get('/surveys/audvis/pick/')
        self.assertContains(page, 'name="HOW"')
        self.assertNotContains(page, 'name="SHEET"')
