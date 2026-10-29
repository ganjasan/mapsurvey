"""Tests for the `question-audience` capability (openspec/specs/question-audience/spec.md).

Change operator-entry (#355): sections, groups and questions say who they are for, and the
one visibility engine judges it per surface.
"""
from django.test import TestCase, override_settings

from survey.models import Organization, SurveyHeader, SurveySection, Question, QuestionGroup
from survey.question_types import SURFACE_OPERATOR, SURFACE_RESPONDENT, audience_allows, normalise_audience
from survey.visibility import compute_visibility, popup_visibility, describe_rule, operator_only


def _survey(name="aud_survey"):
    org = Organization.objects.create(name=f"{name} org")
    return SurveyHeader.objects.create(name=name, organization=org, redirect_url="#")


def _section(survey, name, prev=None, is_head=False, **fields):
    section = SurveySection.objects.create(
        survey_header=survey, name=name, title=name, code=name[:8], is_head=is_head, **fields)
    if prev is not None:
        prev.next_section = section
        prev.save()
        section.prev_section = prev
        section.save()
    return section


def _q(section, code, order, input_type="text_line", **fields):
    if input_type in ("choice", "multichoice") and "choices" not in fields:
        fields["choices"] = [{"code": 1, "name": "Yes"}, {"code": 2, "name": "No"}]
    return Question.objects.create(
        survey_section=section, code=code, order_number=order, name=code,
        input_type=input_type, **fields)


class AudienceDefaultsTest(TestCase):

    def test_default_is_everyone(self):
        """
        GIVEN a question, section and group created without an audience
        WHEN they are read back
        THEN each reads `everyone`
        """
        survey = _survey()
        section = _section(survey, "s1", is_head=True)
        group = QuestionGroup.objects.create(survey_section=section, order_number=1)
        question = _q(section, "Q1", 2)
        for item in (section, group, question):
            item.refresh_from_db()
            self.assertEqual(item.audience, "everyone")

    def test_audience_allows_table(self):
        """
        GIVEN the three audiences and an unknown value
        WHEN they are judged for both surfaces
        THEN everyone admits both, the narrowed ones one each, unknown reads as everyone
        """
        self.assertTrue(audience_allows("everyone", SURFACE_RESPONDENT))
        self.assertTrue(audience_allows("everyone", SURFACE_OPERATOR))
        self.assertFalse(audience_allows("operators", SURFACE_RESPONDENT))
        self.assertTrue(audience_allows("operators", SURFACE_OPERATOR))
        self.assertTrue(audience_allows("respondents", SURFACE_RESPONDENT))
        self.assertFalse(audience_allows("respondents", SURFACE_OPERATOR))
        self.assertTrue(audience_allows("staff", SURFACE_RESPONDENT))
        self.assertEqual(normalise_audience("staff"), "everyone")


class AudienceEngineTest(TestCase):

    def setUp(self):
        self.survey = _survey()
        self.s1 = _section(self.survey, "intro", is_head=True)
        self.ctrl = _q(self.s1, "CTRL", 1, "choice", audience="operators")
        self.plain = _q(self.s1, "PLAIN", 2)
        self.resp_only = _q(self.s1, "RESP", 3, audience="respondents")
        self.s2 = _section(self.survey, "ops", prev=self.s1, audience="operators")
        self.in_ops = _q(self.s2, "INOPS", 1)
        self.s3 = _section(self.survey, "branch", prev=self.s2,
                           visibility_rule={"question_code": "CTRL", "choice_codes": [1]})
        self.in_branch = _q(self.s3, "INBR", 1)

    def test_section_audience_cascades_to_members(self):
        """
        GIVEN an `operators` section holding an `everyone` question
        WHEN visibility is computed for the respondent surface
        THEN neither the section nor the question is visible, and both are for the operator
        """
        resp = compute_visibility(self.survey, {}, surface=SURFACE_RESPONDENT)
        self.assertFalse(resp.is_section_visible(self.s2.id))
        self.assertFalse(resp.is_question_visible(self.in_ops.id))
        self.assertNotIn(self.s2, resp.visible_sections)
        ops = compute_visibility(self.survey, {}, surface=SURFACE_OPERATOR)
        self.assertTrue(ops.is_section_visible(self.s2.id))
        self.assertTrue(ops.is_question_visible(self.in_ops.id))

    def test_each_surface_hides_the_other_audience(self):
        """
        GIVEN an `operators` question and a `respondents` question
        WHEN visibility is computed for each surface
        THEN each surface hides the question meant for the other and records why
        """
        resp = compute_visibility(self.survey, {}, surface=SURFACE_RESPONDENT)
        self.assertFalse(resp.is_question_visible(self.ctrl.id))
        self.assertTrue(resp.is_question_visible(self.resp_only.id))
        self.assertIn(("question", self.ctrl.id), resp.audience_hidden)
        ops = compute_visibility(self.survey, {}, surface=SURFACE_OPERATOR)
        self.assertTrue(ops.is_question_visible(self.ctrl.id))
        self.assertFalse(ops.is_question_visible(self.resp_only.id))
        self.assertTrue(ops.is_question_visible(self.plain.id))

    def test_operator_only_controller_shows_respondents_nothing(self):
        """
        GIVEN a section whose rule depends on an `operators` choice question
        WHEN the controller's answer matches
        THEN the section is hidden for the respondent surface and shown for the operator one
        """
        answers = {"CTRL": [1]}
        self.assertFalse(compute_visibility(self.survey, answers, surface=SURFACE_RESPONDENT)
                         .is_section_visible(self.s3.id))
        self.assertTrue(compute_visibility(self.survey, answers, surface=SURFACE_OPERATOR)
                        .is_section_visible(self.s3.id))

    @override_settings(CONDITIONAL_VISIBILITY=False)
    def test_kill_switch_does_not_disable_audience(self):
        """
        GIVEN CONDITIONAL_VISIBILITY is False
        WHEN visibility is computed for the respondent surface
        THEN the rule-conditioned section shows but the `operators` items stay hidden
        """
        vmap = compute_visibility(self.survey, {})
        self.assertTrue(vmap.is_section_visible(self.s3.id))
        self.assertFalse(vmap.is_question_visible(self.ctrl.id))
        self.assertFalse(vmap.is_section_visible(self.s2.id))

    def test_group_audience_hides_members(self):
        """
        GIVEN an `operators` group with one member question
        WHEN visibility is computed for the respondent surface
        THEN the group and its member are hidden and recorded as audience-hidden
        """
        group = QuestionGroup.objects.create(survey_section=self.s1, order_number=10, audience="operators")
        member = _q(self.s1, "MEM", 11, group=group)
        vmap = compute_visibility(self.survey, {}, surface=SURFACE_RESPONDENT)
        self.assertFalse(vmap.is_group_visible(group.id))
        self.assertFalse(vmap.is_question_visible(member.id))
        self.assertIn(("question", member.id), vmap.audience_hidden)

    def test_operator_only_follows_the_chain(self):
        """
        GIVEN an `everyone` question inside an `operators` section
        WHEN operator_only is asked about it and about a plain question
        THEN the first is operator-only, the second is not
        """
        self.assertTrue(operator_only(self.in_ops))
        self.assertFalse(operator_only(self.plain))


class AudiencePopupTest(TestCase):

    def setUp(self):
        survey = _survey("aud_popup")
        self.section = _section(survey, "map", is_head=True)
        self.parent = _q(self.section, "PT", 1, "point")
        self.sub_all = Question.objects.create(
            survey_section=self.section, parent_question_id=self.parent, code="WHY",
            order_number=1, name="Why", input_type="text_line")
        self.sub_ops = Question.objects.create(
            survey_section=self.section, parent_question_id=self.parent, code="NOTE",
            order_number=2, name="Clerk note", input_type="text_line", audience="operators")

    def test_popup_engine_judges_sub_question_audience(self):
        """
        GIVEN a pop-up with an `everyone` and an `operators` sub-question
        WHEN popup_visibility is computed for each surface
        THEN the operator sub-question is hidden only for respondents
        """
        resp = popup_visibility(self.parent, {}, surface=SURFACE_RESPONDENT)
        self.assertTrue(resp.is_question_visible(self.sub_all.id))
        self.assertFalse(resp.is_question_visible(self.sub_ops.id))
        self.assertTrue(popup_visibility(self.parent, {}, surface=SURFACE_OPERATOR)
                        .is_question_visible(self.sub_ops.id))

    def test_popup_form_leaves_out_other_audience(self):
        """
        GIVEN the same pop-up
        WHEN its answer form is built for each surface
        THEN the respondent form has no field for the operator sub-question
        """
        from survey.forms import SurveySectionAnswerForm
        resp = SurveySectionAnswerForm(initial={}, section=self.section, question=self.parent,
                                       survey_session_id=None)
        self.assertIn("WHY", resp.fields)
        self.assertNotIn("NOTE", resp.fields)
        ops = SurveySectionAnswerForm(initial={}, section=self.section, question=self.parent,
                                      survey_session_id=None, surface=SURFACE_OPERATOR)
        self.assertIn("NOTE", ops.fields)


class AudienceLintTest(TestCase):

    def test_rule_on_operator_only_controller_warns(self):
        """
        GIVEN an `operators` choice question controlling an `everyone` section
        WHEN the editor describes the section's rule
        THEN the badge info carries a warning naming the audience problem
        """
        survey = _survey("aud_lint")
        s1 = _section(survey, "s1", is_head=True)
        _q(s1, "CTRL", 1, "choice", audience="operators")
        s2 = _section(survey, "s2", prev=s1,
                      visibility_rule={"question_code": "CTRL", "choice_codes": [1]})
        info = describe_rule("section", s2, survey)
        self.assertFalse(info["broken"])
        self.assertIn("operators only", info["warning"])

    def test_operator_dependent_gets_no_warning(self):
        """
        GIVEN the same controller and an `operators` dependent section
        WHEN the editor describes the dependent's rule
        THEN there is no warning — operators see both
        """
        survey = _survey("aud_lint2")
        s1 = _section(survey, "s1", is_head=True)
        _q(s1, "CTRL", 1, "choice", audience="operators")
        s2 = _section(survey, "s2", prev=s1, audience="operators",
                      visibility_rule={"question_code": "CTRL", "choice_codes": [1]})
        self.assertNotIn("warning", describe_rule("section", s2, survey))


class AudienceEditingTest(TestCase):
    """The editor sets the audience; a live survey treats it as structure."""

    def setUp(self):
        from django.contrib.auth.models import User
        from survey.models import Membership
        from survey.services.context import Actor
        self.survey = _survey("aud_edit")
        self.user = User.objects.create_user("aud_editor", password="x")
        Membership.objects.create(user=self.user, organization=self.survey.organization, role="owner")
        self.survey.created_by = self.user
        self.survey.save()
        self.section = _section(self.survey, "s1", is_head=True)
        self.question = _q(self.section, "Q1", 1)
        self.group = QuestionGroup.objects.create(survey_section=self.section, order_number=5)
        self.actor = Actor(user=self.user)

    def _publish(self):
        self.survey.status = "published"
        self.survey.save()

    def test_free_workspace_saves_operator_audience(self):
        """
        GIVEN a draft survey of a workspace without Pro
        WHEN a question is saved with audience `operators` through the service
        THEN the save succeeds
        """
        from survey.services import questions as svc
        svc.update(self.actor, self.question, {"audience": "operators"}, partial=True)
        self.question.refresh_from_db()
        self.assertEqual(self.question.audience, "operators")

    def test_post_without_audience_keeps_it(self):
        """
        GIVEN an `operators` question
        WHEN a partial edit that does not name the audience is saved
        THEN the audience is unchanged
        """
        from survey.services import questions as svc
        self.question.audience = "operators"
        self.question.save()
        svc.update(self.actor, self.question, {"name": "Renamed"}, partial=True)
        self.question.refresh_from_db()
        self.assertEqual((self.question.name, self.question.audience), ("Renamed", "operators"))

    def test_live_question_audience_change_is_structural(self):
        """
        GIVEN a published survey
        WHEN a question's audience is changed in place
        THEN the service raises StructureLocked naming the audience
        """
        from survey.services import questions as svc
        from survey.services.errors import StructureLocked
        self._publish()
        with self.assertRaises(StructureLocked) as caught:
            svc.update(self.actor, self.question, {"audience": "operators"}, partial=True)
        self.assertIn("the audience", caught.exception.reasons)

    def test_live_section_and_group_audience_changes_are_structural(self):
        """
        GIVEN a published survey
        WHEN a section's and a group's audience are changed in place
        THEN both are refused as structural
        """
        from survey.services import groups as svc_groups, sections as svc_sections
        from survey.services.errors import StructureLocked
        self._publish()
        with self.assertRaises(StructureLocked):
            svc_sections.update(self.actor, self.section, {"audience": "operators"}, partial=True)
        with self.assertRaises(StructureLocked):
            svc_groups.update(self.actor, self.group, {"audience": "operators"})
        self.group.refresh_from_db()
        self.assertEqual(self.group.audience, "everyone")

    def test_draft_copy_carries_audience_to_publish(self):
        """
        GIVEN a published survey with unpublished changes
        WHEN the copy's question becomes `operators` and the changes are published
        THEN the live question is `operators`
        """
        from survey.versioning import clone_survey_for_draft, publish_draft
        self._publish()
        draft = clone_survey_for_draft(self.survey)
        draft_q = Question.objects.get(survey_section__survey_header=draft, code="Q1")
        draft_q.audience = "operators"
        draft_q.save()
        publish_draft(draft, force=True)
        live_q = Question.objects.get(survey_section__survey_header=self.survey, code="Q1")
        self.assertEqual(live_q.audience, "operators")

    def test_badge_in_the_structure_pane(self):
        """
        GIVEN an `operators` question
        WHEN the editor's survey page renders
        THEN its row carries the Operators only badge and the modal offers the control
        """
        from django.urls import reverse
        self.question.audience = "operators"
        self.question.save()
        self.client.force_login(self.user)
        s = self.client.session
        s["active_org_id"] = self.survey.organization_id
        s.save()
        page = self.client.get(reverse("editor_survey_detail", args=[self.survey.uuid]))
        self.assertContains(page, "audience-badge--operators")
        modal = self.client.get(reverse("editor_question_edit", args=[self.survey.uuid, self.question.id]))
        self.assertContains(modal, 'name="audience"')


class AudienceTravelTest(TestCase):
    """Audience rides copies, archives and the translation table."""

    def setUp(self):
        self.survey = _survey("aud_travel")
        self.section = _section(self.survey, "s1", is_head=True, audience="operators")
        self.group = QuestionGroup.objects.create(survey_section=self.section, order_number=1, audience="respondents")
        self.question = _q(self.section, "TRQ", 2, audience="operators", group=self.group)

    def test_zip_round_trip(self):
        """
        GIVEN a survey with an `operators` section and question and a `respondents` group
        WHEN it is exported and imported
        THEN the imported items carry the same audiences
        """
        from survey.serialization import export_survey_to_zip, import_survey_from_zip
        from io import BytesIO
        buf = BytesIO()
        export_survey_to_zip(self.survey, buf)
        buf.seek(0)
        imported, _warnings = import_survey_from_zip(buf, mode='structure')
        section = SurveySection.objects.get(survey_header=imported)
        self.assertEqual(section.audience, "operators")
        self.assertEqual(QuestionGroup.objects.get(survey_section=section).audience, "respondents")
        self.assertEqual(Question.objects.get(survey_section=section).audience, "operators")

    def test_old_archive_and_unknown_value(self):
        """
        GIVEN question data without `audience`, and question data with an unknown one
        WHEN the questions are created from the archive data
        THEN the first reads everyone silently, the second reads everyone with a report line
        """
        from survey.serialization import _create_question
        warnings = []
        q1 = _create_question(self.section, {"code": "OLD1", "input_type": "text"}, [], {}, warnings=warnings)
        self.assertEqual((q1.audience, warnings), ("everyone", []))
        q2 = _create_question(self.section, {"code": "OLD2", "input_type": "text", "audience": "staff"},
                              [], {}, warnings=warnings)
        self.assertEqual(q2.audience, "everyone")
        self.assertTrue(any("OLD2" in w for w in warnings))

    def test_duplicate_keeps_audience(self):
        """
        GIVEN an `operators` question
        WHEN it is duplicated in the editor's way
        THEN the copy is `operators`
        """
        from survey.cloning import clone_question
        copy = clone_question(self.question, target_section=self.section)
        self.assertEqual(copy.audience, "operators")

    def test_translation_table_lists_operator_items(self):
        """
        GIVEN an `operators` question on a two-language survey
        WHEN the translation table's occurrences are built
        THEN the question's name is one of them
        """
        from survey import translation_table as tt
        self.survey.available_languages = ["en", "de"]
        self.survey.save()
        keys = [o.key for o in tt.occurrences(self.survey, "de")]
        self.assertIn("question:TRQ:name", keys)

    def test_ai_generation_writes_no_audience(self):
        """
        GIVEN a model reply whose section and question carry `audience: operators`
        WHEN the AI draft envelope is built
        THEN neither the section nor the question names an audience, so both import as everyone
        """
        from survey.ai.materialize import build_envelope
        blob = {"sections": [{"title": {"en": "S"}, "audience": "operators", "questions": [
            {"name": {"en": "Q"}, "input_type": "text", "audience": "operators"}]}]}
        envelope = build_envelope(blob, {"name": "AI"}, ["en"])
        section = envelope["survey"]["sections"][0]
        self.assertNotIn("audience", section)
        self.assertNotIn("audience", section["questions"][0])
