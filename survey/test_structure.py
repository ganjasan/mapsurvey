"""Change api-v2-structure (#412): the group service, copies that own their
files, the whole-survey copy, moving a question to another section, and the
editor's Duplicate and "Move to section…" controls.

Specs: `survey-editor` (duplicate a survey, move to section, copies own their
files), `question-groups` (one audited write path, a moved question leaves its
group). REST and MCP over the same services are tested in `api/tests` and
`mcp/tests`.
"""
import json
import shutil
import tempfile

from django.contrib.auth.models import User
from django.contrib.gis.geos import Point
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.test import TestCase, override_settings
from django.urls import reverse

from .cloning import SURVEY_COPY_EXCLUDED_FIELDS
from .models import (
    Answer, AuditLog, LayerObject, LayerObjectAsset, Membership, Organization, Question, QuestionGroup,
    SurveyCollaborator, SurveyHeader, SurveyMapLayer, SurveySection, SurveySession,
)
from .services import groups as svc_groups
from .services import structure as svc_structure
from .services.context import Actor
from .services.errors import AnswersAtRisk, LimitReached, StructureLocked

PNG = (b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f'
       b'\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND'
       b'\xaeB`\x82')


def _org(name, user, role='owner'):
    org = Organization.objects.create(name=name, slug=name.lower())
    Membership.objects.create(user=user, organization=org, role=role)
    return org


def _survey(org, user, name='structure', status='draft'):
    survey = SurveyHeader.objects.create(organization=org, name=name, created_by=user, status=status,
                                         available_languages=['en'], redirect_url='#')
    SurveyCollaborator.objects.create(user=user, survey=survey, role='owner')
    s1 = SurveySection.objects.create(survey_header=survey, name='s1', title='One', code='S1', is_head=True)
    s2 = SurveySection.objects.create(survey_header=survey, name='s2', title='Two', code='S2', prev_section=s1)
    s1.next_section = s2
    s1.save(update_fields=['next_section'])
    return survey, s1, s2


def _q(section, code, order, input_type='text_line', **kw):
    return Question.objects.create(survey_section=section, code=code, order_number=order, name=code,
                                   input_type=input_type, **kw)


def _answer(question, survey, text='x'):
    session = SurveySession.objects.create(survey=survey)
    return Answer.objects.create(survey_session=session, question=question, text=text)


class _Base(TestCase):
    def setUp(self):
        self.media = tempfile.mkdtemp()
        self._media = override_settings(MEDIA_ROOT=self.media)
        self._media.enable()
        self.user = User.objects.create_user(username='structure_owner', password='pass')
        self.org = _org('StructureOrg', self.user)
        self.survey, self.s1, self.s2 = _survey(self.org, self.user)
        self.actor = Actor(user=self.user, ip=None, surface='editor')

    def tearDown(self):
        self._media.disable()
        shutil.rmtree(self.media, ignore_errors=True)


class GroupServiceTest(_Base):
    def test_create_with_members_takes_the_first_members_place(self):
        """
        GIVEN questions Q1..Q4 at the top level of a section
        WHEN a group is created with question_ids [Q2, Q3]
        THEN the order is Q1, the group (Q2, Q3), Q4, and a group_create row is written
        """
        qs = [_q(self.s1, f'Q{i}', i) for i in range(1, 5)]
        group = svc_groups.create(self.actor, self.s1, {'title': 'About you'},
                                  question_ids=[qs[1].pk, qs[2].pk])
        self.assertEqual([q.pk for q in group.members()], [qs[1].pk, qs[2].pk])
        order = sorted([(q.order_number, q.code) for q in Question.objects.filter(survey_section=self.s1)]
                       + [(group.order_number, 'G')])
        self.assertEqual([c for _o, c in order], ['Q1', 'G', 'Q2', 'Q3', 'Q4'])
        self.assertTrue(AuditLog.objects.filter(action='group_create', metadata__group_id=group.pk).exists())

    def test_question_ids_is_the_whole_membership(self):
        """
        GIVEN a group holding Q2 and Q3, and Q4 in another group
        WHEN the first group's question_ids becomes [Q2, Q4]
        THEN its members are exactly Q2, Q4; Q3 stays in the section, ungrouped; the other group is empty
        """
        qs = [_q(self.s1, f'Q{i}', i) for i in range(1, 5)]
        first = svc_groups.create(self.actor, self.s1, {'title': 'A'}, question_ids=[qs[1].pk, qs[2].pk])
        second = svc_groups.create(self.actor, self.s1, {'title': 'B'}, question_ids=[qs[3].pk])
        svc_groups.update(self.actor, first, question_ids=[qs[1].pk, qs[3].pk])
        self.assertEqual([q.pk for q in first.members()], [qs[1].pk, qs[3].pk])
        qs[2].refresh_from_db()
        self.assertIsNone(qs[2].group_id)
        self.assertEqual(qs[2].survey_section, self.s1)
        self.assertEqual(list(second.members()), [])

    def test_foreign_member_is_refused(self):
        """
        GIVEN a question of another section
        WHEN it is named in question_ids
        THEN validation fails on question_ids and no group is left behind
        """
        other = _q(self.s2, 'QX', 1)
        from .services.errors import ValidationFailed
        with self.assertRaises(ValidationFailed) as ctx:
            svc_groups.create(self.actor, self.s1, {'title': 'G'}, question_ids=[other.pk])
        self.assertIn('question_ids', ctx.exception.fields)
        self.assertFalse(QuestionGroup.objects.exists())

    def test_live_wording_in_place_rule_refused(self):
        """
        GIVEN a group on a published survey
        WHEN its title changes, and then its visibility rule
        THEN the title saves; the rule raises StructureLocked naming it
        """
        group = QuestionGroup.objects.create(survey_section=self.s1, title='Old', order_number=1)
        self.survey.status = 'published'
        self.survey.save(update_fields=['status'])
        svc_groups.update(self.actor, group, {'title': 'New'})
        group.refresh_from_db()
        self.assertEqual(group.title, 'New')
        with self.assertRaises(StructureLocked) as ctx:
            svc_groups.update(self.actor, group, visibility_rule={'question_code': 'Q1', 'answered': True})
        self.assertEqual(ctx.exception.reasons, ['visibility rule'])

    def test_editor_group_edit_is_audited(self):
        """
        GIVEN a group and its owner signed in
        WHEN the group modal autosaves a new title
        THEN the editor answers {"ok": true} as before and a group_update row exists
        """
        group = QuestionGroup.objects.create(survey_section=self.s1, title='Old', order_number=1)
        self.client.force_login(self.user)
        response = self.client.post(
            reverse('editor_group_edit', args=[self.survey.uuid, group.pk]),
            {'title': 'Renamed', 'description': '', 'display_style': 'card'})
        self.assertEqual(response.json(), {'ok': True})
        self.assertTrue(AuditLog.objects.filter(action='group_update').exists())


class CopiesOwnTheirFilesTest(_Base):
    def test_paste_into_another_survey_survives_a_purge_of_the_source(self):
        """
        GIVEN a question with an image in survey A, pasted into survey B
        WHEN A is purged from the trash
        THEN B's question has its own file name and the file still exists
        """
        from .trash import purge_survey
        question = _q(self.s1, 'IMG', 1, input_type='image')
        question.image.save('photo.png', ContentFile(PNG))
        other, b1, _b2 = _survey(self.org, self.user, name='other')
        copy = svc_structure.paste_question(self.actor, b1, question)
        self.assertTrue(copy.image.name)
        self.assertNotEqual(copy.image.name, question.image.name)
        purge_survey(self.survey)
        self.assertTrue(default_storage.exists(copy.image.name))

    def test_same_survey_duplicate_shares_the_file(self):
        """
        GIVEN a question with an image
        WHEN it is duplicated in its own survey
        THEN the copy points at the same file (both are purged together)
        """
        question = _q(self.s1, 'IMG', 1, input_type='image')
        question.image.save('photo.png', ContentFile(PNG))
        copy = svc_structure.duplicate_question(self.actor, question)
        self.assertEqual(copy.image.name, question.image.name)
        self.assertTrue(AuditLog.objects.filter(action='question_duplicate').exists())


class DuplicateSurveyTest(_Base):
    def _layer_with_objects(self, n=3):
        layer = SurveyMapLayer.objects.create(survey=self.survey, name='Benches', position=0)
        for i in range(n):
            obj = LayerObject.objects.create(layer=layer, key=f'b{i}', title=f'Bench {i}',
                                             geometry=Point(13.4 + i / 100, 52.5))
        asset = LayerObjectAsset(object=obj, kind='image', title='photo', size_bytes=len(PNG))
        asset.file.save('photo.png', ContentFile(PNG), save=False)
        asset.save()
        return layer, asset

    def test_copy_with_layer_binding_and_no_responses(self):
        """
        GIVEN a published survey with an Objects question bound to a 3-object layer, a shared-map layer,
              a visibility rule and one response
        WHEN it is duplicated
        THEN the copy is a draft "<name> (copy)" owned by the actor, its question is bound to its own
             3-object layer, the shared-map layer comes without objects, the rule still names Q1, the
             asset is a new file, there are no sessions, and the source is unchanged
        """
        layer, asset = self._layer_with_objects()
        controller = _q(self.s1, 'Q1', 1, input_type='choice', choices=[{'code': 1, 'name': 'Yes'}])
        _q(self.s1, 'Q2', 2, visibility_rule={'question_code': 'Q1', 'choice_codes': [1]})
        bound = _q(self.s2, 'OBJ', 1, input_type='layer_objects', layer=layer)
        point = _q(self.s2, 'PT', 2, input_type='point')
        shared = SurveyMapLayer.objects.create(survey=self.survey, name='Marks', source='question',
                                               source_question_code='PT', position=1)
        LayerObject.objects.create(layer=shared, key='s1-1', geometry=Point(13.4, 52.5))
        self.survey.status = 'published'
        self.survey.save(update_fields=['status'])
        _answer(controller, self.survey)

        copy = svc_structure.duplicate_survey(self.actor, self.survey)

        self.assertEqual(copy.status, 'draft')
        self.assertEqual(copy.name, 'structure (copy)')
        self.assertEqual(copy.organization, self.org)
        self.assertTrue(SurveyCollaborator.objects.filter(survey=copy, user=self.user, role='owner').exists())
        new_bound = Question.objects.get(survey_section__survey_header=copy, code='OBJ')
        self.assertNotEqual(new_bound.layer_id, layer.pk)
        self.assertEqual(new_bound.layer.survey_id, copy.pk)
        self.assertEqual(LayerObject.objects.filter(layer=new_bound.layer).count(), 3)
        new_shared = SurveyMapLayer.objects.get(survey=copy, source='question')
        self.assertEqual(new_shared.source_question_code, 'PT')
        self.assertFalse(LayerObject.objects.filter(layer=new_shared).exists())
        self.assertEqual(Question.objects.get(survey_section__survey_header=copy, code='Q2').visibility_rule,
                         {'question_code': 'Q1', 'choice_codes': [1]})
        new_asset = LayerObjectAsset.objects.get(object__layer=new_bound.layer)
        self.assertNotEqual(new_asset.file.name, asset.file.name)
        self.assertTrue(default_storage.exists(new_asset.file.name))
        self.assertFalse(SurveySession.objects.filter(survey=copy).exists())
        sections = list(SurveySection.objects.filter(survey_header=copy).order_by('code'))
        self.assertEqual(sections[0].next_section_id, sections[1].pk)
        self.assertEqual(point.survey_section.survey_header_id, self.survey.pk)
        self.assertEqual(SurveyMapLayer.objects.filter(survey=self.survey).count(), 2)
        self.assertTrue(AuditLog.objects.filter(action='survey_duplicate', survey_uuid=copy.uuid).exists())

    def test_every_header_field_travels_but_the_exclusions(self):
        """
        GIVEN a survey whose every plain header field differs from the model default
        WHEN it is duplicated
        THEN every concrete plain field is equal on the copy except the listed exclusions
        """
        from django.contrib.gis.db.models import GeometryField
        from django.db import models as dj
        for f in SurveyHeader._meta.concrete_fields:
            if f.primary_key or f.is_relation or f.name in SURVEY_COPY_EXCLUDED_FIELDS:
                continue
            current = getattr(self.survey, f.attname)
            if isinstance(f, GeometryField):
                value = Point(7.0, 7.0)
            elif f.choices:
                value = next(c for c, _ in f.flatchoices if c != current)
            elif isinstance(f, dj.BooleanField):
                value = not current
            elif isinstance(f, dj.JSONField):
                value = ['poked'] if isinstance(current, list) else {'poked': f.name}
            elif isinstance(f, (dj.IntegerField, dj.PositiveIntegerField)):
                value = (current or 0) + 7
            else:
                value = f'{f.name} poked'[: (f.max_length or 100)]
            setattr(self.survey, f.attname, value)
        self.survey.save()
        copy = svc_structure.duplicate_survey(self.actor, self.survey)
        for f in SurveyHeader._meta.concrete_fields:
            if f.primary_key or f.is_relation or f.name in SURVEY_COPY_EXCLUDED_FIELDS:
                continue
            self.assertEqual(f.value_from_object(copy), f.value_from_object(self.survey), f.name)

    def test_attachment_cap(self):
        """
        GIVEN layer attachments recorded as more than 200 MB
        WHEN the survey is duplicated
        THEN LimitReached and no new survey
        """
        _layer, asset = self._layer_with_objects(1)
        LayerObjectAsset.objects.filter(pk=asset.pk).update(size_bytes=201 * 1024 * 1024)
        before = SurveyHeader.objects.count()
        with self.assertRaises(LimitReached):
            svc_structure.duplicate_survey(self.actor, self.survey)
        self.assertEqual(SurveyHeader.objects.count(), before)

    def test_editor_duplicate_and_roles(self):
        """
        GIVEN a workspace editor and a workspace viewer
        WHEN each posts Duplicate from the dashboard
        THEN the editor lands on the copy's Build page; the viewer gets 403 and sees no Duplicate item
        """
        editor = User.objects.create_user(username='ws_editor', password='pass')
        Membership.objects.create(user=editor, organization=self.org, role='editor')
        SurveyCollaborator.objects.create(user=editor, survey=self.survey, role='viewer')
        viewer = User.objects.create_user(username='ws_viewer', password='pass')
        Membership.objects.create(user=viewer, organization=self.org, role='viewer')
        url = reverse('editor_survey_duplicate', args=[self.survey.uuid])

        self.client.force_login(editor)
        response = self.client.post(url)
        copy = SurveyHeader.objects.exclude(pk=self.survey.pk).get(name='structure (copy)')
        self.assertRedirects(response, reverse('editor_survey_detail', args=[copy.uuid]),
                             fetch_redirect_response=False)

        self.client.force_login(viewer)
        self.assertEqual(self.client.post(url).status_code, 403)
        session = self.client.session
        session['active_org_id'] = self.org.pk
        session.save()
        page = self.client.get(reverse('editor'))
        self.assertNotContains(page, url)


class MoveToSectionTest(_Base):
    def test_move_keeps_answers_and_leaves_the_group(self):
        """
        GIVEN an answered, grouped question in section One
        WHEN it is moved to the start of section Two
        THEN it is first in Two, ungrouped, its answer is still there, One is renumbered, and it is audited
        """
        q1 = _q(self.s1, 'Q1', 1)
        moved = _q(self.s1, 'Q2', 2)
        group = svc_groups.create(self.actor, self.s1, {'title': 'G'}, question_ids=[moved.pk])
        target = _q(self.s2, 'Q3', 1)
        _answer(moved, self.survey)

        result = svc_structure.move_question(self.actor, moved, section=self.s2, position=0)

        moved.refresh_from_db()
        self.assertEqual(moved.survey_section, self.s2)
        self.assertIsNone(moved.group_id)
        self.assertEqual(Answer.objects.filter(question=moved).count(), 1)
        target.refresh_from_db()
        self.assertLess(moved.order_number, target.order_number)
        self.assertTrue(QuestionGroup.objects.filter(pk=group.pk).exists())
        self.assertEqual(result.removed_rules, [])
        q1.refresh_from_db()
        self.assertEqual(q1.order_number, 0)
        self.assertTrue(AuditLog.objects.filter(action='question_move').exists())

    @override_settings(CONDITIONAL_VISIBILITY=True)
    def test_move_below_a_dependent_clears_the_rule(self):
        """
        GIVEN Q2 in section Two shown only when Q1 (section One) is Yes
        WHEN Q1 is moved to the end of section Two
        THEN Q2's rule is cleared and named in removed_rules
        """
        q1 = _q(self.s1, 'Q1', 1, input_type='choice', choices=[{'code': 1, 'name': 'Yes'}])
        q2 = _q(self.s2, 'Q2', 1, visibility_rule={'question_code': 'Q1', 'choice_codes': [1]})
        result = svc_structure.move_question(self.actor, q1, section=self.s2)
        q2.refresh_from_db()
        self.assertIsNone(q2.visibility_rule)
        self.assertEqual(result.removed_rules, ['Q2'])

    def test_into_a_popup_needs_acknowledgement(self):
        """
        GIVEN an answered text question and a point question in another section
        WHEN it is moved into the point question's pop-up without acknowledgement
        THEN AnswersAtRisk and nothing moved
        """
        question = _q(self.s1, 'Q1', 1)
        parent = _q(self.s2, 'PT', 1, input_type='point')
        _answer(question, self.survey)
        with self.assertRaises(AnswersAtRisk):
            svc_structure.move_question(self.actor, question, parent=parent)
        question.refresh_from_db()
        self.assertEqual(question.survey_section, self.s1)

    def test_live_survey_is_locked(self):
        """
        GIVEN a published survey
        WHEN a question is moved to another section
        THEN StructureLocked
        """
        question = _q(self.s1, 'Q1', 1)
        self.survey.status = 'published'
        self.survey.save(update_fields=['status'])
        with self.assertRaises(StructureLocked):
            svc_structure.move_question(self.actor, question, section=self.s2)

    def test_editor_move_to_section(self):
        """
        GIVEN the owner on the Build page
        WHEN "Move to section…" posts section Two for a question of One
        THEN the editor answers ok with no removed rules and the question is in Two;
             the row shows the control
        """
        question = _q(self.s1, 'Q1', 1)
        self.client.force_login(self.user)
        response = self.client.post(reverse('editor_question_move', args=[self.survey.uuid, question.pk]),
                                    json.dumps({'section_id': self.s2.pk}), content_type='application/json')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json(), {'ok': True, 'removed_rules': []})
        question.refresh_from_db()
        self.assertEqual(question.survey_section, self.s2)
        page = self.client.get(reverse('editor_section_detail', args=[self.survey.uuid, self.s2.pk]))
        self.assertContains(page, 'move-section-btn')

    def test_build_page_highlights_the_section_it_opened_on(self):
        """
        GIVEN a two-section survey
        WHEN the Build page opens with ?section=<second> (where "Move to section…" returns the creator)
        THEN the second section's sidebar row is the active one, and without the parameter the first is
        """
        self.client.force_login(self.user)
        url = reverse('editor_survey_detail', args=[self.survey.uuid])
        page = self.client.get(url, {'section': self.s2.pk}).content.decode()
        self.assertRegex(page, rf'class="section-item active"\s+data-section-id="{self.s2.pk}"')
        self.assertNotRegex(page, rf'class="section-item active"\s+data-section-id="{self.s1.pk}"')
        first = self.client.get(url).content.decode()
        self.assertRegex(first, rf'class="section-item active"\s+data-section-id="{self.s1.pk}"')
