"""Question groups (openspec change question-groups, #340).

One module for the capability, as billing/tests does per capability: model and
ordering, the visibility engine's group host, the respondent page and POST, the
editor, serialization and lifecycle, comments.
"""
import json
import re

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from survey.groups import group_runs, next_order, runs_for, shift_down
from survey.models import (
    Answer, Organization, Question, QuestionGroup, QuestionGroupTranslation,
    SurveyHeader, SurveySection,
)
from survey.visibility import compute_visibility, popup_visibility, popup_rules_for_client


def _survey(name="qg", status="published", languages=None):
    org = Organization.objects.create(name=f"{name} org")
    survey = SurveyHeader.objects.create(
        name=name, organization=org, status=status,
        available_languages=languages or [], redirect_url="#")
    section = SurveySection.objects.create(
        survey_header=survey, name="s1", title="S1", code="S1", is_head=True)
    return survey, section


def _q(section, code, order, input_type="text_line", parent=None, group=None, **kw):
    return Question.objects.create(
        survey_section=section, code=code, order_number=order, name=kw.pop("name", code),
        input_type=input_type, parent_question_id=parent, group=group, **kw)


def _place_fixture(section, group_rule=True, style="card"):
    """The #340 acceptance shape: a point question whose pop-up asks "Type of place",
    then the group "Your visit" (three questions) ruled by "Type of place answered",
    then an ungrouped comment."""
    point = _q(section, "PT", 0, "point", name="My places")
    kind = _q(section, "KIND", 0, "choice", parent=point, name="Type of place",
              choices=[{"code": 1, "name": "Park"}, {"code": 2, "name": "Shop"}])
    group = QuestionGroup.objects.create(
        survey_section=section, parent_question=point, code="G_VISIT", title="Your visit",
        description="<p>About the last time</p>", display_style=style, order_number=1,
        visibility_rule={"question_code": "KIND", "answered": True} if group_rule else None)
    often = _q(section, "OFTEN", 2, "text_line", parent=point, group=group, name="How often?")
    when = _q(section, "WHEN", 3, "text_line", parent=point, group=group, name="When?")
    who = _q(section, "WHO", 4, "text_line", parent=point, group=group, name="Who with?")
    note = _q(section, "NOTE", 5, "text", parent=point, name="Comment")
    return {"point": point, "kind": kind, "group": group, "often": often, "when": when,
            "who": who, "note": note}


class QuestionGroupModelTest(TestCase):
    """Model, the continuous order and group_runs (design D1, D2)."""

    def setUp(self):
        self.survey, self.section = _survey("qg_model")

    def test_deleting_a_group_keeps_members_in_place(self):
        """
        GIVEN a section Q1, [G: Q2, Q3], Q4
        WHEN the group row is deleted
        THEN Q2 and Q3 still exist, belong to no group, and keep their order numbers
        """
        g = QuestionGroup.objects.create(survey_section=self.section, order_number=1, title="G")
        _q(self.section, "Q1", 0)
        q2 = _q(self.section, "Q2", 2, group=g)
        q3 = _q(self.section, "Q3", 3, group=g)
        _q(self.section, "Q4", 4)
        g.delete()
        q2.refresh_from_db()
        q3.refresh_from_db()
        self.assertIsNone(q2.group_id)
        self.assertEqual((q2.order_number, q3.order_number), (2, 3))

    def test_group_runs_in_order(self):
        """
        GIVEN Q1, [G: Q2, Q3], Q4 on one sequence
        WHEN the runs are built
        THEN they are (None:[Q1]), (G:[Q2,Q3]), (None:[Q4])
        """
        g = QuestionGroup.objects.create(survey_section=self.section, order_number=1, title="G")
        _q(self.section, "Q1", 0)
        _q(self.section, "Q2", 2, group=g)
        _q(self.section, "Q3", 3, group=g)
        _q(self.section, "Q4", 4)
        runs = runs_for(self.section)
        self.assertEqual(
            [(r[0] and r[0].title, [q.code for q in r[1]]) for r in runs],
            [(None, ["Q1"]), ("G", ["Q2", "Q3"]), (None, ["Q4"])])

    def test_non_contiguous_members_repeat_the_header_and_lose_nothing(self):
        """
        GIVEN a member of G found after an ungrouped question that sits inside G's run
        WHEN the runs are built
        THEN every question appears once and G opens a second run
        """
        g = QuestionGroup.objects.create(survey_section=self.section, order_number=0, title="G")
        _q(self.section, "A", 1, group=g)
        _q(self.section, "B", 2)
        _q(self.section, "C", 3, group=g)
        runs = runs_for(self.section)
        self.assertEqual([(r[0] and r[0].title, [q.code for q in r[1]]) for r in runs],
                         [("G", ["A"]), (None, ["B"]), ("G", ["C"])])

    def test_empty_group_yields_empty_run(self):
        """
        GIVEN a group with no members
        WHEN the runs are built
        THEN it is one empty run (the editor shows it; the respondent form drops it)
        """
        QuestionGroup.objects.create(survey_section=self.section, order_number=0, title="G")
        self.assertEqual([(r[0].title, r[1]) for r in group_runs([], [*self.section.question_groups.all()])],
                         [("G", [])])

    def test_next_order_and_shift_count_groups(self):
        """
        GIVEN a question at 0 and a group at 1
        WHEN next_order is asked and then everything after 0 is shifted
        THEN next_order is 2 and the group moves to 2
        """
        _q(self.section, "Q1", 0)
        g = QuestionGroup.objects.create(survey_section=self.section, order_number=1)
        self.assertEqual(next_order(self.section), 2)
        shift_down(self.section, None, 0)
        g.refresh_from_db()
        self.assertEqual(g.order_number, 2)

    def test_translation_falls_back_to_primary(self):
        """
        GIVEN a group titled "Your visit" with a Portuguese title and no Portuguese description
        WHEN translated text is asked for pt
        THEN the title is Portuguese and the description falls back to the primary text
        """
        g = QuestionGroup.objects.create(survey_section=self.section, title="Your visit",
                                         description="<p>About</p>")
        QuestionGroupTranslation.objects.create(group=g, language="pt", title="A sua visita")
        self.assertEqual(g.get_translated_title("pt"), "A sua visita")
        self.assertEqual(g.get_translated_description("pt"), "<p>About</p>")

    def test_codes_are_generated_and_distinct(self):
        """
        GIVEN two groups created without a code
        WHEN they are saved
        THEN both have a G_ code and the codes differ
        """
        a = QuestionGroup.objects.create(survey_section=self.section)
        b = QuestionGroup.objects.create(survey_section=self.section)
        self.assertTrue(a.code.startswith("G_"))
        self.assertNotEqual(a.code, b.code)


class GroupVisibilityEngineTest(TestCase):
    """survey/visibility.py with the group host kind (spec conditional-visibility)."""

    def setUp(self):
        self.survey, self.section = _survey("qg_engine")
        self.ctrl = _q(self.section, "CTRL", 0, "choice",
                       choices=[{"code": 1, "name": "Yes"}, {"code": 2, "name": "No"}])
        self.group = QuestionGroup.objects.create(
            survey_section=self.section, code="G1", order_number=1, title="G",
            visibility_rule={"question_code": "CTRL", "choice_codes": [1]})
        self.m1 = _q(self.section, "M1", 2, "choice", group=self.group,
                     choices=[{"code": 1, "name": "a"}])
        self.m2 = _q(self.section, "M2", 3, group=self.group,
                     visibility_rule={"question_code": "CTRL", "choice_codes": [1]})
        self.after = _q(self.section, "AFTER", 4,
                        visibility_rule={"question_code": "M1", "answered": True})

    def test_group_rule_hides_every_member(self):
        """
        GIVEN a group shown when CTRL = Yes
        WHEN CTRL is No
        THEN the group and both members are hidden
        """
        vmap = compute_visibility(self.survey, {"CTRL": [2]})
        self.assertFalse(vmap.is_group_visible(self.group.id))
        self.assertFalse(vmap.is_question_visible(self.m1.id))
        self.assertFalse(vmap.is_question_visible(self.m2.id))

    def test_group_shown_when_rule_matches(self):
        """
        GIVEN the same group
        WHEN CTRL is Yes
        THEN the group and its members are shown
        """
        vmap = compute_visibility(self.survey, {"CTRL": [1]})
        self.assertTrue(vmap.is_group_visible(self.group.id))
        self.assertTrue(vmap.is_question_visible(self.m1.id))
        self.assertTrue(vmap.is_question_visible(self.m2.id))

    def test_cascade_past_a_hidden_member(self):
        """
        GIVEN a later question shown when member M1 is answered
        WHEN the group is hidden although M1 carries an answer
        THEN the later question is hidden too (a hidden controller satisfies nothing)
        """
        vmap = compute_visibility(self.survey, {"CTRL": [2], "M1": [1]})
        self.assertFalse(vmap.is_question_visible(self.after.id))

    def test_member_rule_on_top_of_group_rule(self):
        """
        GIVEN a visible group whose member M2 has its own rule that does not match
        WHEN CTRL is Yes but M2's rule asks for something else
        THEN M2 is hidden and M1 is shown
        """
        self.m2.visibility_rule = {"question_code": "CTRL", "choice_codes": [2]}
        self.m2.save()
        vmap = compute_visibility(self.survey, {"CTRL": [1]})
        self.assertTrue(vmap.is_question_visible(self.m1.id))
        self.assertFalse(vmap.is_question_visible(self.m2.id))

    def test_answered_mode(self):
        """
        GIVEN a group shown when CTRL is answered (any option)
        WHEN CTRL is unanswered, then answered No
        THEN the group is hidden, then shown
        """
        self.group.visibility_rule = {"question_code": "CTRL", "answered": True}
        self.group.save()
        self.assertFalse(compute_visibility(self.survey, {}).is_group_visible(self.group.id))
        self.assertTrue(compute_visibility(self.survey, {"CTRL": [2]}).is_group_visible(self.group.id))

    def test_controller_inside_the_group_is_broken_and_fails_open(self):
        """
        GIVEN the group's rule names its own member M1
        WHEN visibility is computed
        THEN the rule is broken, the group is shown, and the brokenness is keyed ('group', id)
        """
        self.group.visibility_rule = {"question_code": "M1", "choice_codes": [1]}
        self.group.save()
        vmap = compute_visibility(self.survey, {})
        self.assertTrue(vmap.is_group_visible(self.group.id))
        self.assertIn(("group", self.group.id), vmap.broken)

    def test_forward_controller_is_broken(self):
        """
        GIVEN the group's rule names a question after the group
        WHEN visibility is computed
        THEN the rule is broken and the group is shown
        """
        _q(self.section, "LATE", 9, "choice", choices=[{"code": 1, "name": "x"}])
        self.group.visibility_rule = {"question_code": "LATE", "choice_codes": [1]}
        self.group.save()
        vmap = compute_visibility(self.survey, {})
        self.assertIn(("group", self.group.id), vmap.broken)
        self.assertTrue(vmap.is_question_visible(self.m1.id))

    def test_describe_and_dependents(self):
        """
        GIVEN the group ruled by CTRL
        WHEN the editor badge filters run
        THEN the group badge reads "if CTRL = Yes" and CTRL counts the group among its dependents
        """
        from survey.templatetags.question_utils import visibility_dependents, visibility_info
        with override_settings(CONDITIONAL_VISIBILITY=True):
            self.assertEqual(visibility_info(self.group, self.survey)["label"], "if CTRL = Yes")
            # M2 and AFTER(no: AFTER names M1) — M2 and the group name CTRL.
            self.assertEqual(visibility_dependents(self.ctrl, self.survey), 2)


class GroupPopupVisibilityTest(TestCase):
    """Pop-up groups are judged per feature (spec conditional-visibility)."""

    def setUp(self):
        self.survey, self.section = _survey("qg_popup_engine")
        self.f = _place_fixture(self.section)

    def test_group_hidden_until_type_is_picked(self):
        """
        GIVEN "Your visit" ruled by "Type of place answered"
        WHEN one feature has no type and another has Park
        THEN the first hides the group and its members, the second shows them
        """
        none = popup_visibility(self.f["point"], {})
        park = popup_visibility(self.f["point"], {"KIND": [1]})
        self.assertFalse(none.is_group_visible(self.f["group"].id))
        self.assertFalse(none.is_question_visible(self.f["often"].id))
        self.assertTrue(none.is_question_visible(self.f["note"].id))
        self.assertTrue(park.is_question_visible(self.f["who"].id))

    def test_client_rules_put_the_group_before_its_members(self):
        """
        GIVEN the group rule and a member with its own rule
        WHEN the client rules are built
        THEN the group key comes before the member key
        """
        self.f["when"].visibility_rule = {"question_code": "KIND", "choice_codes": [1]}
        self.f["when"].save()
        with override_settings(CONDITIONAL_VISIBILITY=True):
            keys = list(popup_rules_for_client(self.f["point"]))
        self.assertEqual(keys, ["group:G_VISIT", "WHEN"])


class GroupRespondentTest(TestCase):
    """The respondent page and POST (spec question-groups, conditional-visibility)."""

    def setUp(self):
        self.survey, self.section = _survey("qg_resp")
        self.url = f"/surveys/{self.survey.uuid}/s1/"

    def _feature(self, x, y, props):
        return json.dumps({"type": "Feature", "geometry": {"type": "Point", "coordinates": [x, y]},
                           "properties": {"question_id": "PT", **props}})

    def _child_codes(self):
        sid = self.client.session["survey_session_id"]
        return {a.question.code for a in Answer.objects.filter(
            survey_session_id=sid, parent_answer_id__isnull=False).select_related("question")}

    def test_section_renders_a_card_group_around_its_questions(self):
        """
        GIVEN Q1 then the card group "Your school day" with two questions
        WHEN the section is opened
        THEN the group element carries its title and description and wraps both cards, after Q1
        """
        g = QuestionGroup.objects.create(survey_section=self.section, code="G_DAY", order_number=1,
                                         title="Your school day", description="<p>A normal week</p>")
        _q(self.section, "Q1", 0, name="Age")
        _q(self.section, "Q2", 2, group=g, name="How do you get there")
        _q(self.section, "Q3", 3, group=g, name="How long")
        html = self.client.get(self.url).content.decode()
        start = html.index('data-group-code="G_DAY"')
        self.assertIn("question-group--card", html[start - 100:start])
        self.assertIn("Your school day", html[start:])
        self.assertIn("<p>A normal week</p>", html[start:])
        self.assertLess(html.index('data-field-name="Q1"'), start)
        self.assertLess(start, html.index('data-field-name="Q2"'))

    def test_title_is_escaped(self):
        """
        GIVEN a group title containing markup
        WHEN the section is opened
        THEN the title is escaped
        """
        g = QuestionGroup.objects.create(survey_section=self.section, order_number=0,
                                         title="<b>bold</b>")
        _q(self.section, "Q1", 1, group=g)
        html = self.client.get(self.url).content.decode()
        self.assertIn("&lt;b&gt;bold&lt;/b&gt;", html)

    def test_collapsible_renders_closed_with_a_count(self):
        """
        GIVEN a collapsible group of two questions
        WHEN the section is opened
        THEN its toggle is aria-expanded=false, the body is hidden and the count reads "2 questions"
        """
        g = QuestionGroup.objects.create(survey_section=self.section, code="G_C", order_number=0,
                                         title="More", display_style="collapsible")
        _q(self.section, "Q1", 1, group=g)
        _q(self.section, "Q2", 2, group=g)
        html = self.client.get(self.url).content.decode()
        self.assertRegex(html, r'class="question-group__toggle" aria-expanded="false"')
        self.assertRegex(html, r'id="qg-body-G_C" hidden')
        self.assertIn("2 questions", html)

    def test_popup_html_contains_the_group_and_ships_its_rule(self):
        """
        GIVEN the #340 acceptance pop-up
        WHEN the section is opened
        THEN the pop-up HTML wraps the three questions in "Your visit" and the rule rides the
             pop-up rule map keyed group:<code>
        """
        _place_fixture(self.section)
        html = self.client.get(self.url).content.decode()
        forms = json.loads(re.search(r'id="sq-forms-data"[^>]*>(.*?)</script>', html, re.S).group(1))
        popup = forms["PT"]
        self.assertIn('data-group-code="G_VISIT"', popup)
        g_at = popup.index('data-group-code="G_VISIT"')
        for code in ("OFTEN", "WHEN", "WHO"):
            self.assertLess(g_at, popup.index(f'data-field-name="{code}"'))
        self.assertLess(popup.index('data-field-name="KIND"'), g_at)
        rules = json.loads(re.search(r'data-popup-visibility-rules="([^"]*)"', html)
                           .group(1).replace("&quot;", '"'))
        self.assertEqual(rules, {"group:G_VISIT": {"question_code": "KIND", "answered": True}})

    def test_acceptance_group_answers_only_after_a_type(self):
        """
        GIVEN "Your visit" ruled by "Type of place answered"
        WHEN one feature has no type and the group filled, another has Park and the group filled
        THEN the first stores only the comment, the second stores the type and three group answers
        """
        _place_fixture(self.section)
        self.client.get(self.url)
        self.client.post(self.url, {"PT": "|".join([
            self._feature(13.4, 52.5, {"OFTEN": ["x"], "WHEN": ["x"], "WHO": ["x"], "NOTE": ["n"]}),
        ]) + "|"})
        self.assertEqual(self._child_codes(), {"NOTE"})
        self.client.post(self.url, {"PT": "|".join([
            self._feature(13.4, 52.5, {"KIND": ["1"], "OFTEN": ["d"], "WHEN": ["m"], "WHO": ["f"]}),
        ]) + "|"})
        self.assertEqual(self._child_codes(), {"KIND", "OFTEN", "WHEN", "WHO"})

    def test_hidden_section_group_answers_are_discarded(self):
        """
        GIVEN a section group shown when CTRL = Yes, with a member answered in the POST
        WHEN CTRL is posted as No
        THEN the member's answer is not stored
        """
        _q(self.section, "CTRL", 0, "choice", choices=[{"code": 1, "name": "Yes"}, {"code": 2, "name": "No"}])
        g = QuestionGroup.objects.create(survey_section=self.section, code="G1", order_number=1,
                                         visibility_rule={"question_code": "CTRL", "choice_codes": [1]})
        _q(self.section, "M1", 2, group=g)
        self.client.get(self.url)
        self.client.post(self.url, {"CTRL": "2", "M1": "should go"})
        sid = self.client.session["survey_session_id"]
        self.assertFalse(Answer.objects.filter(survey_session_id=sid, question__code="M1").exists())
        self.client.post(self.url, {"CTRL": "1", "M1": "kept"})
        self.assertEqual(Answer.objects.get(survey_session_id=sid, question__code="M1").text, "kept")

    def test_same_section_group_rule_ships_and_members_stay_in_the_dom(self):
        """
        GIVEN a section group ruled by an earlier question of the same section
        WHEN the section is opened with nothing answered
        THEN the member is in the page (the client hides it) and the rule is keyed group:<code>
        """
        _q(self.section, "CTRL", 0, "choice", choices=[{"code": 1, "name": "Yes"}])
        g = QuestionGroup.objects.create(survey_section=self.section, code="G1", order_number=1,
                                         visibility_rule={"question_code": "CTRL", "choice_codes": [1]})
        _q(self.section, "M1", 2, group=g)
        html = self.client.get(self.url).content.decode()
        self.assertIn('data-field-name="M1"', html)
        rules = json.loads(re.search(r'data-visibility-rules="([^"]*)"', html)
                           .group(1).replace("&quot;", '"'))
        self.assertEqual(rules, {"group:G1": {"question_code": "CTRL", "choice_codes": [1]}})

    def test_group_hidden_from_an_earlier_section_is_not_rendered(self):
        """
        GIVEN a group in section 2 ruled by an unanswered choice in section 1
        WHEN section 2 is opened
        THEN neither the group nor its member is rendered
        """
        _q(self.section, "CTRL", 0, "choice", choices=[{"code": 1, "name": "Yes"}])
        s2 = SurveySection.objects.create(survey_header=self.survey, name="s2", title="S2", code="S2",
                                          prev_section=self.section)
        self.section.next_section = s2
        self.section.save()
        g = QuestionGroup.objects.create(survey_section=s2, code="G2", order_number=0, title="Hidden G",
                                         visibility_rule={"question_code": "CTRL", "choice_codes": [1]})
        _q(s2, "M1", 1, group=g)
        _q(s2, "FREE", 2)
        self.client.get(self.url)
        html = self.client.get(f"/surveys/{self.survey.uuid}/s2/").content.decode()
        self.assertNotIn("G2", html)
        self.assertNotIn('data-field-name="M1"', html)
        self.assertIn('data-field-name="FREE"', html)

    def test_translated_title(self):
        """
        GIVEN a bilingual survey with a Portuguese group title
        WHEN a respondent opens the section in Portuguese
        THEN the group title is Portuguese
        """
        self.survey.available_languages = ["en", "pt"]
        self.survey.save()
        g = QuestionGroup.objects.create(survey_section=self.section, order_number=0, title="Your visit")
        QuestionGroupTranslation.objects.create(group=g, language="pt", title="A sua visita")
        _q(self.section, "Q1", 1, group=g)
        session = self.client.session
        session["survey_language"] = "pt"
        session.save()
        html = self.client.get(self.url + "?lang=pt").content.decode()
        self.assertIn("A sua visita", html)


class GroupEditorTest(TestCase):
    """Editor endpoints (spec question-groups: authoring, delete, live split)."""

    def setUp(self):
        from survey.models import Membership
        self.survey, self.section = _survey("qg_editor", status="draft")
        self.user = User.objects.create_user(username="qg_editor", password="pw")
        Membership.objects.create(user=self.user, organization=self.survey.organization, role="owner")
        self.client.force_login(self.user)
        self.base = f"/editor/surveys/{self.survey.uuid}"

    def _reorder(self, items, parent=None):
        return self.client.post(f"{self.base}/items/reorder/", data=json.dumps({
            "section_id": self.section.id, "parent_id": parent, "items": items,
        }), content_type="application/json")

    def test_add_group_to_section_opens_its_modal(self):
        """
        GIVEN a section with one question
        WHEN "Add group" is clicked
        THEN a group exists after the question and the group modal is returned
        """
        _q(self.section, "Q1", 1)
        r = self.client.post(f"{self.base}/sections/{self.section.id}/groups/new/")
        self.assertEqual(r.status_code, 200)
        group = QuestionGroup.objects.get(survey_section=self.section)
        self.assertIsNone(group.parent_question)
        self.assertEqual(group.order_number, 2)
        self.assertIn("data-group-form", r.content.decode())
        self.assertEqual(r["HX-Trigger"], "groupsChanged")

    def test_add_group_under_a_point_question(self):
        """
        GIVEN a point question with one sub-question
        WHEN "Add group" under it is clicked
        THEN the group belongs to that pop-up and lands after the sub-question
        """
        point = _q(self.section, "PT", 0, "point")
        _q(self.section, "S1", 1, parent=point)
        self.client.post(f"{self.base}/sections/{self.section.id}/groups/new/", {"parent_id": point.id})
        group = QuestionGroup.objects.get(survey_section=self.section)
        self.assertEqual(group.parent_question, point)
        self.assertEqual(group.order_number, 2)

    def test_section_list_renders_group_row_with_members(self):
        """
        GIVEN a group "Your visit" with two questions
        WHEN the section panel is rendered
        THEN the group row shows "Group · 2" and nests both question rows
        """
        g = QuestionGroup.objects.create(survey_section=self.section, order_number=0, title="Your visit")
        _q(self.section, "Q1", 1, group=g, name="First")
        _q(self.section, "Q2", 2, group=g, name="Second")
        html = self.client.get(f"{self.base}/sections/{self.section.id}/").content.decode()
        row = html[html.index(f'data-group-id="{g.id}"'):]
        self.assertIn("Group · 2", row)
        self.assertLess(row.index("group-question-list"), row.index("First"))

    def test_autosave_edits_content_and_rule(self):
        """
        GIVEN a draft survey with a choice question and a group after it
        WHEN the group modal autosaves a title, a description with a script, a style and a rule
        THEN they are stored, the script is gone, and the answer is JSON ok
        """
        _q(self.section, "CTRL", 0, "choice", choices=[{"code": 1, "name": "Yes"}])
        g = QuestionGroup.objects.create(survey_section=self.section, order_number=1)
        with override_settings(CONDITIONAL_VISIBILITY=True):
            r = self.client.post(f"{self.base}/groups/{g.id}/edit/", {
                "autosave": "1", "title": "Your visit",
                "description": "<p>Hi</p><script>alert(1)</script>", "display_style": "collapsible",
                "visibility_mode": "conditional", "visibility_question": "CTRL",
                "visibility_match": "answered",
            })
        self.assertEqual(r.json(), {"ok": True})
        g.refresh_from_db()
        self.assertEqual((g.title, g.display_style), ("Your visit", "collapsible"))
        self.assertNotIn("script", g.description)
        self.assertEqual(g.visibility_rule, {"question_code": "CTRL", "answered": True})

    def test_autosave_rejects_unknown_style_with_422(self):
        """
        GIVEN a group
        WHEN the autosave posts an unknown display style
        THEN the answer is 422 JSON and nothing changes
        """
        g = QuestionGroup.objects.create(survey_section=self.section, title="Keep")
        r = self.client.post(f"{self.base}/groups/{g.id}/edit/", {
            "autosave": "1", "title": "Changed", "display_style": "carousel"})
        self.assertEqual(r.status_code, 422)
        g.refresh_from_db()
        self.assertEqual(g.title, "Keep")

    def test_translation_saved_and_coerced(self):
        """
        GIVEN a bilingual survey
        WHEN the modal posts a Portuguese title (ignored: the modal is a read-only
             mirror since change translation-table) and the Translations tab
             writes a title and a description with a script
        THEN the modal post creates no row, and the tab's row holds the title and
             a script-free description
        """
        from survey import translation_table as tt
        from survey.services.context import Actor

        self.survey.available_languages = ["en", "pt"]
        self.survey.save()
        g = QuestionGroup.objects.create(survey_section=self.section, title="Visit", code="G_VISIT",
                                         description="<p>Tell us</p>")
        self.client.post(f"{self.base}/groups/{g.id}/edit/", {
            "autosave": "1", "title": "Visit", "description": "<p>Tell us</p>", "display_style": "card",
            "translation_pt_title": "Visita", "translation_pt_description": "<script>x</script>ok"})
        self.assertFalse(QuestionGroupTranslation.objects.filter(group=g, language="pt").exists())
        report = tt.apply(Actor(user=self.user), self.survey, "pt", {
            "group:G_VISIT:title": "Visita", "group:G_VISIT:description": "<script>x</script>ok"})
        self.assertEqual((report.filled, report.unmatched), (2, []))
        t = QuestionGroupTranslation.objects.get(group=g, language="pt")
        self.assertEqual(t.title, "Visita")
        self.assertNotIn("<script", t.description)

    def test_delete_only_the_group_keeps_members_in_place(self):
        """
        GIVEN Q1, [G: Q2, Q3]
        WHEN the group is deleted with the default choice
        THEN Q2 and Q3 remain, ungrouped, with their order numbers
        """
        _q(self.section, "Q1", 0)
        g = QuestionGroup.objects.create(survey_section=self.section, order_number=1)
        _q(self.section, "Q2", 2, group=g)
        _q(self.section, "Q3", 3, group=g)
        r = self.client.post(f"{self.base}/groups/{g.id}/delete/", {"with_questions": ""})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["HX-Retarget"], "#section-content")
        self.assertFalse(QuestionGroup.objects.exists())
        self.assertEqual(list(Question.objects.filter(group__isnull=True).order_by("order_number")
                              .values_list("code", flat=True)), ["Q1", "Q2", "Q3"])

    def test_delete_with_questions_needs_acknowledgement_when_answered(self):
        """
        GIVEN a group whose two questions hold 3 answers
        WHEN "delete with questions" is posted without, then with, the acknowledgement
        THEN the first answer is 409 reporting 3 and nothing is gone; the second deletes all
        """
        from survey.models import SurveySession
        g = QuestionGroup.objects.create(survey_section=self.section, order_number=0)
        q1 = _q(self.section, "Q1", 1, group=g)
        q2 = _q(self.section, "Q2", 2, group=g)
        session = SurveySession.objects.create(survey=self.survey)
        for q, text in ((q1, "a"), (q1, "b"), (q2, "c")):
            Answer.objects.create(survey_session=session, question=q, text=text)
        url = f"{self.base}/groups/{g.id}/delete/"
        r = self.client.post(url, {"with_questions": "1"})
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.json()["answers_at_risk"], 3)
        self.assertEqual(Question.objects.count(), 2)
        self.client.post(url, {"with_questions": "1", "confirm_delete_answers": "true"})
        self.assertFalse(Question.objects.exists())
        self.assertFalse(QuestionGroup.objects.exists())
        self.assertFalse(Answer.objects.exists())

    def test_delete_dialog_offers_the_choice_only_with_members(self):
        """
        GIVEN an empty group and a group with 2 questions
        WHEN their delete dialogs open
        THEN the empty one has no choice; the other offers "only the group" checked and "its 2 questions"
        """
        empty = QuestionGroup.objects.create(survey_section=self.section, order_number=0)
        full = QuestionGroup.objects.create(survey_section=self.section, order_number=1)
        _q(self.section, "Q1", 2, group=full)
        _q(self.section, "Q2", 3, group=full)
        e = self.client.get(f"{self.base}/groups/{empty.id}/delete/").content.decode()
        f = self.client.get(f"{self.base}/groups/{full.id}/delete/").content.decode()
        self.assertNotIn('value="keep"', e)
        self.assertRegex(f, r'value="keep" checked')
        self.assertIn("Delete the group and its 2 questions", f)

    def test_reorder_moves_a_question_into_and_out_of_a_group(self):
        """
        GIVEN Q1, [G: Q2], Q4
        WHEN Q4 is dropped into G after Q2, then Q2 is dropped to the top
        THEN the order and the memberships follow each drop
        """
        q1 = _q(self.section, "Q1", 0)
        g = QuestionGroup.objects.create(survey_section=self.section, order_number=1)
        q2 = _q(self.section, "Q2", 2, group=g)
        q4 = _q(self.section, "Q4", 3)
        self.assertEqual(self._reorder([{"q": q1.id}, {"g": g.id, "q": [q2.id, q4.id]}]).status_code, 204)
        q4.refresh_from_db()
        self.assertEqual((q4.group_id, q4.order_number), (g.id, 3))
        self._reorder([{"q": q2.id}, {"q": q1.id}, {"g": g.id, "q": [q4.id]}])
        q2.refresh_from_db()
        g.refresh_from_db()
        self.assertEqual((q2.group_id, q2.order_number, g.order_number), (None, 0, 2))

    def test_reorder_refuses_foreign_ids(self):
        """
        GIVEN a question of another section
        WHEN a reorder of this section names it
        THEN the answer is 400 and nothing is renumbered
        """
        q1 = _q(self.section, "Q1", 5)
        other = SurveySection.objects.create(survey_header=self.survey, name="s2", code="S2")
        foreign = _q(other, "F1", 0)
        self.assertEqual(self._reorder([{"q": foreign.id}, {"q": q1.id}]).status_code, 400)
        q1.refresh_from_db()
        self.assertEqual(q1.order_number, 5)

    def test_reorder_refuses_a_subquestion_in_the_top_list(self):
        """
        GIVEN a sub-question of a point question
        WHEN a top-level reorder names it
        THEN the answer is 400
        """
        point = _q(self.section, "PT", 0, "point")
        sub = _q(self.section, "S1", 0, parent=point)
        self.assertEqual(self._reorder([{"q": point.id}, {"q": sub.id}]).status_code, 400)

    def test_duplicate_keeps_group_and_paste_lands_ungrouped_last(self):
        """
        GIVEN [G: Q1] and Q2
        WHEN Q1 is duplicated
        THEN the copy is in G right after Q1 and Q2 moved down one
        """
        g = QuestionGroup.objects.create(survey_section=self.section, order_number=0)
        q1 = _q(self.section, "Q1", 1, group=g)
        q2 = _q(self.section, "Q2", 2)
        self.client.post(f"{self.base}/questions/{q1.id}/duplicate/")
        copy = Question.objects.exclude(pk__in=[q1.pk, q2.pk]).get()
        q2.refresh_from_db()
        self.assertEqual((copy.group_id, copy.order_number, q2.order_number), (g.id, 2, 3))

    def test_new_question_after_a_group_is_numbered_past_it(self):
        """
        GIVEN a section whose last item is an empty group at order 4
        WHEN a question is created
        THEN it gets order 5, after the group, ungrouped
        """
        QuestionGroup.objects.create(survey_section=self.section, order_number=4)
        self.client.post(f"{self.base}/sections/{self.section.id}/questions/new/",
                         {"input_type": "text", "name": "After", "draft": "1"})
        q = Question.objects.get(name="After")
        self.assertEqual((q.order_number, q.group_id), (5, None))

    def test_preview_renders_unsaved_style(self):
        """
        GIVEN a card group with one question
        WHEN the modal previews display_style=collapsible
        THEN the frame renders a collapsible group with the posted title
        """
        g = QuestionGroup.objects.create(survey_section=self.section, title="Saved", code="G_P")
        _q(self.section, "Q1", 1, group=g)
        html = self.client.post(f"{self.base}/groups/{g.id}/preview/",
                                {"title": "Typed", "display_style": "collapsible"}).content.decode()
        self.assertIn("question-group--collapsible", html)
        self.assertIn("Typed", html)

    def test_add_question_inside_a_section_group(self):
        """
        GIVEN [G: Q1] followed by Q2
        WHEN a question is created from "Add question to group" (type picked)
        THEN it belongs to G right after Q1, Q2 moves down, and the list is re-rendered
        """
        g = QuestionGroup.objects.create(survey_section=self.section, order_number=0, title="G")
        _q(self.section, "Q1", 1, group=g)
        q2 = _q(self.section, "Q2", 2)
        modal = self.client.get(f"{self.base}/sections/{self.section.id}/questions/new/?group={g.id}")
        self.assertIn(f"?group={g.id}", modal.content.decode())
        self.assertIn("New question in group", modal.content.decode())
        r = self.client.post(f"{self.base}/sections/{self.section.id}/questions/new/?group={g.id}",
                             {"input_type": "text", "name": "Inside", "draft": "1"})
        self.assertIn("groupsChanged", r["HX-Trigger"])
        new = Question.objects.get(name="Inside")
        q2.refresh_from_db()
        self.assertEqual((new.group_id, new.order_number, q2.order_number), (g.id, 2, 3))

    def test_add_subquestion_inside_a_popup_group(self):
        """
        GIVEN a point question whose pop-up holds [G: S1] then S2
        WHEN a sub-question is created with ?group=G
        THEN it joins G after S1 and S2 moves down
        """
        point = _q(self.section, "PT", 0, "point")
        g = QuestionGroup.objects.create(survey_section=self.section, parent_question=point, order_number=0)
        _q(self.section, "S1", 1, parent=point, group=g)
        s2 = _q(self.section, "S2", 2, parent=point)
        self.client.post(f"{self.base}/questions/{point.id}/subquestions/new/?group={g.id}",
                         {"input_type": "choice", "name": "Inside", "color": "#000000",
                          "choices_json": json.dumps([{"code": 1, "name": "A"}])})
        new = Question.objects.get(name="Inside")
        s2.refresh_from_db()
        self.assertEqual((new.group_id, new.order_number, s2.order_number), (g.id, 2, 3))

    def test_group_of_another_bucket_is_ignored(self):
        """
        GIVEN a pop-up group
        WHEN a top-level question is created naming it
        THEN the question is created ungrouped at the end of the section
        """
        point = _q(self.section, "PT", 0, "point")
        g = QuestionGroup.objects.create(survey_section=self.section, parent_question=point, order_number=0)
        self.client.post(f"{self.base}/sections/{self.section.id}/questions/new/?group={g.id}",
                         {"input_type": "text", "name": "Top", "draft": "1"})
        self.assertIsNone(Question.objects.get(name="Top").group_id)

    def test_preview_of_an_empty_group_shows_examples_between_neighbours(self):
        """
        GIVEN a group with no questions
        WHEN its preview renders
        THEN two example questions sit inside it, marked as examples, between faded neighbours
        """
        g = QuestionGroup.objects.create(survey_section=self.section, title="Empty", code="G_E")
        html = self.client.post(f"{self.base}/groups/{g.id}/preview/", {"display_style": "card"}).content.decode()
        self.assertIn("Example questions", html)
        self.assertEqual(html.count('class="qg-context"'), 2)
        self.assertLess(html.index("A question before the group"), html.index('data-group-code="G_E"'))
        self.assertLess(html.index('data-group-code="G_E"'), html.index("A question after the group"))

    def test_live_survey_retitle_in_place_and_structure_refused(self):
        """
        GIVEN a published survey with a group and a choice question before it
        WHEN the title is autosaved, then a rule is autosaved, then a group is added
        THEN the title is saved in place, the rule is refused (422), the add is 403
        """
        self.survey.status = "published"
        self.survey.save()
        _q(self.section, "CTRL", 0, "choice", choices=[{"code": 1, "name": "Yes"}])
        g = QuestionGroup.objects.create(survey_section=self.section, order_number=1, title="Old")
        with override_settings(CONDITIONAL_VISIBILITY=True, LIVE_SURVEY_EDITING=True):
            r = self.client.post(f"{self.base}/groups/{g.id}/edit/", {
                "autosave": "1", "title": "New", "display_style": "card"})
            self.assertEqual(r.status_code, 200)
            r = self.client.post(f"{self.base}/groups/{g.id}/edit/", {
                "autosave": "1", "title": "New", "display_style": "card",
                "visibility_mode": "conditional", "visibility_question": "CTRL",
                "visibility_match": "answered"})
            self.assertEqual(r.status_code, 422)
            r = self.client.post(f"{self.base}/sections/{self.section.id}/groups/new/")
            self.assertEqual(r.status_code, 403)
        g.refresh_from_db()
        self.assertEqual((g.title, g.visibility_rule), ("New", None))


class QuestionMoveTest(TestCase):
    """Moving a question between the section and a pop-up (spec question-groups, D7b)."""

    def setUp(self):
        from survey.models import Membership
        self.survey, self.section = _survey("qg_move", status="draft")
        user = User.objects.create_user(username="qg_move", password="pw")
        Membership.objects.create(user=user, organization=self.survey.organization, role="owner")
        self.client.force_login(user)
        self.point = _q(self.section, "PT", 0, "point")
        self.kind = _q(self.section, "KIND", 0, "choice", parent=self.point,
                       choices=[{"code": 1, "name": "Park"}])
        self.group = QuestionGroup.objects.create(
            survey_section=self.section, parent_question=self.point, order_number=1, title="Visit")
        self.inside = _q(self.section, "IN", 2, parent=self.point, group=self.group)
        self.age = _q(self.section, "AGE", 1, name="Your age")

    def _move(self, question, parent, items, **extra):
        body = {"section_id": self.section.id, "parent_id": parent, "items": items, **extra}
        return self.client.post(f"/editor/surveys/{self.survey.uuid}/questions/{question.id}/move/",
                                data=json.dumps(body), content_type="application/json")

    def test_section_question_into_a_popup_group(self):
        """
        GIVEN an unanswered section question "Your age"
        WHEN it is dropped into the pop-up group "Visit" after its question
        THEN it is a sub-question of the point, in "Visit", after IN
        """
        r = self._move(self.age, self.point.id, [
            {"q": self.kind.id}, {"g": self.group.id, "q": [self.inside.id, self.age.id]}])
        self.assertEqual(r.status_code, 200)
        self.age.refresh_from_db()
        self.assertEqual((self.age.parent_question_id_id, self.age.group_id, self.age.order_number),
                         (self.point.id, self.group.id, 3))

    def test_subquestion_out_to_the_section(self):
        """
        GIVEN a sub-question inside the pop-up group
        WHEN it is dropped at the top of the section
        THEN it is a top-level question, ungrouped, first
        """
        r = self._move(self.inside, None, [{"q": self.inside.id}, {"q": self.point.id}, {"q": self.age.id}])
        self.assertEqual(r.status_code, 200)
        self.inside.refresh_from_db()
        self.assertEqual((self.inside.parent_question_id_id, self.inside.group_id, self.inside.order_number),
                         (None, None, 0))

    def test_answered_question_needs_acknowledgement_and_loses_answers(self):
        """
        GIVEN "Your age" with 2 answers
        WHEN it is moved into the pop-up without, then with the acknowledgement
        THEN the first is 409 reporting 2 and nothing moves; the second moves it and deletes them
        """
        from survey.models import SurveySession
        session = SurveySession.objects.create(survey=self.survey)
        for t in ("30", "40"):
            Answer.objects.create(survey_session=session, question=self.age, text=t)
        items = [{"q": self.kind.id}, {"q": self.age.id}, {"g": self.group.id, "q": [self.inside.id]}]
        r = self._move(self.age, self.point.id, items)
        self.assertEqual((r.status_code, r.json()["answers_at_risk"]), (409, 2))
        self.age.refresh_from_db()
        self.assertIsNone(self.age.parent_question_id_id)
        r = self._move(self.age, self.point.id, items, confirm_delete_answers="true")
        self.assertEqual(r.status_code, 200)
        self.assertFalse(Answer.objects.filter(question=self.age).exists())

    def test_geo_question_is_refused_by_a_popup(self):
        """
        GIVEN a polygon question in the section
        WHEN it is dropped into the point's pop-up
        THEN the move is refused and the polygon stays top-level
        """
        poly = _q(self.section, "POLY", 2, "polygon")
        r = self._move(poly, self.point.id, [{"q": poly.id}])
        self.assertEqual(r.status_code, 409)
        self.assertIn("blocked", r.json())
        poly.refresh_from_db()
        self.assertIsNone(poly.parent_question_id_id)

    def test_rules_broken_by_the_move_are_removed_and_named(self):
        """
        GIVEN a section choice question that controls a later section question, and has its own rule
        WHEN the controller is moved into the pop-up
        THEN both rules are removed and both hosts are named in removed_rules
        """
        ctrl = _q(self.section, "CTRL", 2, "choice", name="Controller",
                  choices=[{"code": 1, "name": "Yes"}],
                  visibility_rule={"question_code": "AGE", "answered": True})
        dep = _q(self.section, "DEP", 3, name="Dependent",
                 visibility_rule={"question_code": "CTRL", "choice_codes": [1]})
        with override_settings(CONDITIONAL_VISIBILITY=True):
            r = self._move(ctrl, self.point.id, [{"q": self.kind.id}, {"g": self.group.id, "q": [self.inside.id]},
                                                  {"q": ctrl.id}])
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["removed_rules"], ["Controller", "Dependent"])
        ctrl.refresh_from_db()
        dep.refresh_from_db()
        self.assertIsNone(ctrl.visibility_rule)
        self.assertIsNone(dep.visibility_rule)

    def test_live_survey_refuses_the_move(self):
        """
        GIVEN a published survey
        WHEN a move is posted
        THEN it is refused with 403
        """
        self.survey.status = "published"
        self.survey.save()
        r = self._move(self.age, self.point.id, [{"q": self.age.id}])
        self.assertEqual(r.status_code, 403)


class GroupSerializationTest(TestCase):
    """ZIP export/import and copies (spec question-groups: groups travel)."""

    def setUp(self):
        self.survey, self.section = _survey("qg_zip", status="draft", languages=["en", "pt"])
        self.f = _place_fixture(self.section)
        QuestionGroupTranslation.objects.create(group=self.f["group"], language="pt", title="A sua visita")
        _q(self.section, "CTRL", 1, "choice", choices=[{"code": 1, "name": "Yes"}])
        self.sg = QuestionGroup.objects.create(
            survey_section=self.section, code="G_SEC", order_number=2, title="Section group",
            display_style="plain", visibility_rule={"question_code": "CTRL", "choice_codes": [1]})
        _q(self.section, "SM1", 3, group=self.sg)

    def _roundtrip(self, mutate=None):
        import io
        import zipfile
        from survey.serialization import export_survey_to_zip, import_survey_from_zip
        out = io.BytesIO()
        export_survey_to_zip(self.survey, out, mode="structure")
        out.seek(0)
        with zipfile.ZipFile(out) as zf:
            data = json.loads(zf.read("survey.json"))
        data["survey"]["name"] = "qg_zip_imported"
        if mutate:
            mutate(data)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("survey.json", json.dumps(data))
        buf.seek(0)
        return import_survey_from_zip(buf)

    def test_round_trip_keeps_groups_members_rules_and_translations(self):
        """
        GIVEN a survey with a pop-up group (rule, translation) and a section group (rule)
        WHEN it is exported and imported
        THEN both groups exist with their style, order, rules, translation and members
        """
        survey, warnings = self._roundtrip()
        groups = {g.title: g for g in QuestionGroup.objects.filter(survey_section__survey_header=survey)}
        visit, sec = groups["Your visit"], groups["Section group"]
        self.assertEqual(visit.parent_question.input_type, "point")
        self.assertEqual(sorted(visit.questions.values_list("name", flat=True)),
                         ["How often?", "When?", "Who with?"])
        self.assertEqual(visit.visibility_rule["answered"], True)
        self.assertEqual(visit.get_translated_title("pt"), "A sua visita")
        self.assertEqual((sec.display_style, sec.order_number), ("plain", 2))
        self.assertEqual(sec.visibility_rule["choice_codes"], [1])
        self.assertEqual(sec.questions.count(), 1)

    def test_archive_without_groups_imports_unchanged(self):
        """
        GIVEN an archive with every group key removed
        WHEN it is imported
        THEN the questions import ungrouped and no group exists
        """
        def strip(data):
            for s in data["survey"]["sections"]:
                s.pop("groups", None)
                for q in s["questions"]:
                    q.pop("group", None)
                    q.pop("sub_question_groups", None)
                    for sq in q.get("sub_questions", []):
                        sq.pop("group", None)
        survey, _ = self._roundtrip(strip)
        self.assertFalse(QuestionGroup.objects.filter(survey_section__survey_header=survey).exists())
        self.assertEqual(Question.objects.filter(survey_section__survey_header=survey).count(), 8)

    def test_unknown_group_reference_is_a_warning(self):
        """
        GIVEN an archive whose question names a group that is not in it
        WHEN it is imported
        THEN the question imports ungrouped and the report names it
        """
        def break_ref(data):
            for s in data["survey"]["sections"]:
                for q in s["questions"]:
                    if q["code"] == "SM1":
                        q["group"] = "G_NOPE"
        survey, warnings = self._roundtrip(break_ref)
        self.assertTrue(any("G_NOPE" in w for w in warnings))

    def test_duplicating_the_point_question_remaps_the_group_rule(self):
        """
        GIVEN the point question whose pop-up group is ruled by its "Type of place"
        WHEN it is duplicated in the editor
        THEN the copy has its own group, ruled by the copy's "Type of place", with three members
        """
        from survey.cloning import clone_question
        copy = clone_question(self.f["point"], target_section=self.section, regenerate_code=True)
        group = copy.sub_question_groups.get()
        kind_copy = copy.subQuestions().get(name="Type of place")
        self.assertEqual(group.visibility_rule["question_code"], kind_copy.code)
        self.assertEqual(group.questions.count(), 3)
        self.assertNotEqual(group.code, self.f["group"].code)

    def test_duplicating_the_section_keeps_the_section_group(self):
        """
        GIVEN the section group ruled by CTRL in the same section
        WHEN the section is duplicated
        THEN the copied group is ruled by the copied CTRL and holds the copied member
        """
        from survey.cloning import clone_section
        new_section = clone_section(self.section, target_survey=self.survey, insert_after=self.section)
        g = new_section.question_groups.get(parent_question__isnull=True)
        ctrl_copy = new_section.question_set.get(name="CTRL")
        self.assertEqual(g.visibility_rule["question_code"], ctrl_copy.code)
        self.assertEqual(g.questions.get().name, "SM1")

    def test_draft_publish_keeps_groups_and_answers(self):
        """
        GIVEN a published survey with an answered grouped question
        WHEN a draft is created, a group added in it, and the draft published
        THEN the live survey has the original and the new group, same codes, and the answer survives
        """
        from survey.models import SurveySession
        from survey.versioning import clone_survey_for_draft, publish_draft
        self.survey.status = "published"
        self.survey.save()
        session = SurveySession.objects.create(survey=self.survey)
        Answer.objects.create(survey_session=session, question=Question.objects.get(code="SM1"), text="kept")
        draft = clone_survey_for_draft(self.survey)
        d_section = draft.surveysection_set.get()
        self.assertEqual(set(QuestionGroup.objects.filter(survey_section=d_section).values_list("code", flat=True)),
                         {"G_SEC", "G_VISIT"})
        QuestionGroup.objects.create(survey_section=d_section, code="G_NEW", order_number=9, title="New")
        publish_draft(draft, force=True)
        live_codes = set(QuestionGroup.objects.filter(
            survey_section__survey_header=self.survey).values_list("code", flat=True))
        self.assertEqual(live_codes, {"G_SEC", "G_VISIT", "G_NEW"})
        self.assertTrue(Answer.objects.filter(text="kept").exists())
        self.assertEqual(QuestionGroup.objects.get(survey_section__survey_header=self.survey, code="G_SEC")
                         .questions.get().code, "SM1")


class GroupCommentsTest(TestCase):
    """Comment threads anchored to a group (spec question-groups)."""

    def test_thread_on_a_group_is_counted_on_its_row(self):
        """
        GIVEN a group of a survey
        WHEN a thread is anchored to it by the page id
        THEN the anchor is stored by code and open_counts reports 1 under group:<code>
        """
        from survey import comments as svc
        from survey.models import CommentThread
        survey, section = _survey("qg_comments", status="draft")
        g = QuestionGroup.objects.create(survey_section=section, code="G_CM", title="Your visit")
        fields = svc.anchor_fields(survey, "group", g.id)
        self.assertEqual(fields, {"anchor_kind": "group", "group_code": "G_CM"})
        thread = CommentThread.objects.create(survey=survey, **fields)
        self.assertEqual(svc.open_counts(survey)["group"]["G_CM"], 1)
        anchor = svc.resolve_anchor(thread)
        self.assertEqual((anchor.label, anchor.exists), ("Your visit", True))


class GroupReadSurfacesTest(TestCase):
    """Groups change nothing on read surfaces; text surfaces see group text."""

    def test_export_columns_are_the_same_with_and_without_the_group(self):
        """
        GIVEN the #340 pop-up with an answered feature
        WHEN the observations are collected with the group, and again after deleting it
        THEN the column lists are identical
        """
        from django.contrib.gis.geos import Point
        from survey import export
        from survey.models import SurveySession
        survey, section = _survey("qg_export")
        f = _place_fixture(section)
        session = SurveySession.objects.create(survey=survey)
        parent = Answer.objects.create(survey_session=session, question=f["point"], point=Point(13.4, 52.5))
        Answer.objects.create(survey_session=session, question=f["kind"], parent_answer_id=parent, selected_choices=[1])
        for key in ("often", "when", "who"):
            Answer.objects.create(survey_session=session, question=f[key], parent_answer_id=parent, text="x")
        with_group = export.observation_columns(export.collect(survey, [(survey, None)]))
        f["group"].delete()
        without = export.observation_columns(export.collect(survey, [(survey, None)]))
        self.assertEqual(with_group, without)
        self.assertTrue({"How often?", "When?", "Who with?"} <= set(with_group))

    def test_translation_gaps_and_screening_read_group_text(self):
        """
        GIVEN a bilingual survey with a titled group lacking its Portuguese title
        WHEN gaps and screening text are computed
        THEN the gap names the group and the screened text includes its title
        """
        from survey.content_screening import collect_text
        from survey.translation_gaps import survey_translation_gaps
        survey, section = _survey("qg_text", languages=["en", "pt"])
        QuestionGroup.objects.create(survey_section=section, title="Claim your prize")
        gaps = survey_translation_gaps(survey)
        self.assertIn({"label": "Group: Claim your prize", "missing": ["pt"]}, gaps)
        self.assertIn("Claim your prize", " ".join(t for _l, t in collect_text(survey).texts))
