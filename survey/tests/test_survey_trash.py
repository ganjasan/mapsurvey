"""Tests for the `survey-trash` capability (openspec/specs/survey-trash/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase, Client, override_settings
from django.contrib.auth.models import User
from django.contrib.gis.geos import Point
from django.utils import timezone
from unittest.mock import patch
import re
from survey.models import SurveyHeader, SurveySection, Question, SurveySession, Membership
from django.core.management import call_command
from survey.models import AuditLog
from survey.tests.helpers import _make_org, _validated_geojson_text, _zones_geojson


class SurveyTrashTest(TestCase):
    """Tests for the trash lifecycle: hide, restore, purge."""

    def setUp(self):
        """Set up an owner with a published survey that has a session."""
        self.client = Client()
        self.org = _make_org('TrashOrg')
        self.user = User.objects.create_user(username='trashuser', password='testpass123')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.survey = SurveyHeader.objects.create(
            name="trash_test_survey", organization=self.org, status='published',
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name="trash_section", code="TS", is_head=True,
        )
        self.session = SurveySession.objects.create(survey=self.survey)
        self.client.login(username='trashuser', password='testpass123')

    def _trash(self):
        self.client.post(f'/editor/delete/{self.survey.uuid}/')
        self.survey.refresh_from_db()

    def test_trashed_hidden_from_dashboard(self):
        """
        GIVEN a trashed survey
        WHEN the owner opens the dashboard
        THEN the survey is not in the survey list but appears in the Trash section
        """
        self._trash()
        # ?dashboard=1: with the survey trashed the org has no live surveys, so
        # a bare /editor/ now redirects new creators to the create page. This
        # test is about what the dashboard shows, so ask for it explicitly.
        response = self.client.get('/editor/?dashboard=1')

        self.assertEqual(response.status_code, 200)
        self.assertNotIn(self.survey, response.context['survey_headers'])
        self.assertIn(self.survey, response.context['trashed_surveys'])

    def test_trashed_public_url_404(self):
        """
        GIVEN a published survey that was trashed
        WHEN a respondent opens its public URL
        THEN the response is 404
        """
        self._trash()
        response = self.client.get(f'/surveys/{self.survey.uuid}/')

        self.assertEqual(response.status_code, 404)

    def test_trashed_editor_endpoint_404(self):
        """
        GIVEN a trashed survey
        WHEN the owner opens a regular editor endpoint for it
        THEN the response is 404 (only trash endpoints may touch it)
        """
        self._trash()
        response = self.client.get(f'/editor/surveys/{self.survey.uuid}/')

        self.assertEqual(response.status_code, 404)

    def test_restore_returns_survey(self):
        """
        GIVEN a trashed published survey
        WHEN the owner restores it
        THEN it reappears on the dashboard with its original status and public URL works
        """
        self._trash()
        response = self.client.post(f'/editor/restore/{self.survey.uuid}/')

        self.assertEqual(response.status_code, 302)
        self.survey.refresh_from_db()
        self.assertIsNone(self.survey.deleted_at)
        self.assertEqual(self.survey.status, 'published')
        dashboard = self.client.get('/editor/')
        self.assertIn(self.survey, dashboard.context['survey_headers'])
        public = self.client.get(f'/surveys/{self.survey.uuid}/')
        self.assertIn(public.status_code, (200, 302))  # entry redirects to first section

    def test_purge_rejects_non_trashed(self):
        """
        GIVEN a survey that is not in trash
        WHEN the owner posts to the purge endpoint
        THEN nothing is deleted
        """
        response = self.client.post(f'/editor/purge/{self.survey.uuid}/')

        self.assertEqual(response.status_code, 302)
        self.assertTrue(SurveyHeader.objects.filter(pk=self.survey.pk).exists())

    def test_purge_removes_media_files(self):
        """
        GIVEN a trashed survey with a cover image and a question image
        WHEN the survey is purged
        THEN both files are removed from storage
        """
        from django.core.files.base import ContentFile
        gif = b'GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;'
        self.survey.cover_image.save('trash_test_cover.gif', ContentFile(gif), save=True)
        question = Question.objects.create(
            survey_section=self.section, code="Q_IMG", name="img", input_type="text",
        )
        question.image.save('trash_test_qimg.gif', ContentFile(gif), save=True)
        cover_name, image_name = self.survey.cover_image.name, question.image.name
        storage = self.survey.cover_image.storage
        self.assertTrue(storage.exists(cover_name))
        self.assertTrue(storage.exists(image_name))

        self._trash()
        self.client.post(f'/editor/purge/{self.survey.uuid}/')

        self.assertFalse(storage.exists(cover_name))
        self.assertFalse(storage.exists(image_name))

    def test_purge_deletes_archived_versions(self):
        """
        GIVEN a trashed survey with an archived version carrying a session
        WHEN the survey is purged
        THEN the archived version and its session are deleted too
        """
        archived = SurveyHeader.objects.create(
            name="trash_test_survey_v1", organization=self.org,
            canonical_survey=self.survey, is_canonical=False, version_number=1,
        )
        archived_session = SurveySession.objects.create(survey=archived)

        self._trash()
        self.client.post(f'/editor/purge/{self.survey.uuid}/')

        self.assertFalse(SurveyHeader.objects.filter(pk=archived.pk).exists())
        self.assertFalse(SurveySession.objects.filter(pk=archived_session.pk).exists())


class PurgeSurveyWithLayersTest(TestCase):
    """Purging a survey that owns reference layers.

    `Question.layer` is PROTECT so that deleting a layer on its own refuses and
    names the bound question. Django evaluates PROTECT while the collector is
    still gathering rows, without exempting objects that are themselves being
    collected — so before this change that protection also blocked the
    survey-wide purge, where the question goes too (PostHog 01a0a513, ten
    ProtectedErrors from one creator's Delete-forever).
    """

    def setUp(self):
        """Set up an owner with a trashed survey owning a layer a question is bound to."""
        from survey.models import SurveyMapLayer, LayerObject

        self.org = _make_org('PurgeLayerOrg')
        self.user = User.objects.create_user(username='purgelayeruser', password='testpass123')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.survey = SurveyHeader.objects.create(
            name="purge_layer_survey", organization=self.org, status='published',
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name="s1", title="S1", code="S1", is_head=True,
        )
        geojson, count, _ = _validated_geojson_text(_zones_geojson().encode())
        self.layer = SurveyMapLayer.objects.create(
            survey=self.survey, name="Zones", geojson=geojson, feature_count=count,
            size_bytes=len(geojson),
        )
        self.obj = LayerObject.objects.create(
            layer=self.layer, key='o-1', title='Zone 1', position=1,
            geometry=Point(13.4, 52.5),
        )
        self.question = Question.objects.create(
            survey_section=self.section, code="Q_OBJ", name="Routen",
            input_type="layer_objects", layer=self.layer,
        )

    def test_purge_survey_with_layer_bound_question(self):
        """
        GIVEN a trashed survey whose layer_objects question is bound to its own reference layer
        WHEN the survey is purged
        THEN the survey, the question, the layer and its objects are all deleted without raising
        """
        from survey.models import SurveyMapLayer, LayerObject
        from survey.trash import purge_survey

        purge_survey(self.survey)

        self.assertFalse(SurveyHeader.objects.filter(pk=self.survey.pk).exists())
        self.assertFalse(Question.objects.filter(pk=self.question.pk).exists())
        self.assertFalse(SurveyMapLayer.objects.filter(pk=self.layer.pk).exists())
        self.assertFalse(LayerObject.objects.filter(pk=self.obj.pk).exists())

    def test_purge_through_the_editor_endpoint(self):
        """
        GIVEN a trashed survey owning a layer its question is bound to
        WHEN the owner posts Delete forever
        THEN the survey is gone — the ten 500s a creator hit on this path cannot recur
        """
        from survey.models import SurveyMapLayer

        self.client.login(username='purgelayeruser', password='testpass123')
        self.client.post(f'/editor/delete/{self.survey.uuid}/')
        response = self.client.post(f'/editor/purge/{self.survey.uuid}/')

        self.assertEqual(response.status_code, 302)
        self.assertFalse(SurveyHeader.objects.filter(pk=self.survey.pk).exists())
        self.assertFalse(SurveyMapLayer.objects.filter(pk=self.layer.pk).exists())

    def test_purge_with_draft_copy_borrowing_the_layer(self):
        """
        GIVEN a published survey with a live draft copy whose question borrows the canonical's layer
        WHEN the survey is purged
        THEN both headers, the draft's question and the layer are deleted
        """
        from survey.models import SurveyMapLayer
        from survey.trash import purge_survey

        draft = SurveyHeader.objects.create(
            name="[draft] purge_layer_survey", organization=self.org,
            published_version=self.survey, status='draft',
        )
        draft_section = SurveySection.objects.create(
            survey_header=draft, name="s1", title="S1", code="S1", is_head=True,
        )
        draft_question = Question.objects.create(
            survey_section=draft_section, code="Q_OBJ", name="Routen",
            input_type="layer_objects", layer=self.layer,
        )

        purge_survey(self.survey)

        self.assertFalse(SurveyHeader.objects.filter(pk=draft.pk).exists())
        self.assertFalse(Question.objects.filter(pk=draft_question.pk).exists())
        self.assertFalse(SurveyMapLayer.objects.filter(pk=self.layer.pk).exists())

    def test_purge_leaves_another_surveys_binding_alone(self):
        """
        GIVEN a second survey whose question is bound to its own layer
        WHEN the first survey is purged
        THEN the second survey's question keeps its layer binding
        """
        from survey.models import SurveyMapLayer
        from survey.trash import purge_survey

        other = SurveyHeader.objects.create(
            name="other_survey", organization=self.org, status='published',
        )
        other_section = SurveySection.objects.create(
            survey_header=other, name="s1", title="S1", code="S1", is_head=True,
        )
        geojson, count, _ = _validated_geojson_text(_zones_geojson().encode())
        other_layer = SurveyMapLayer.objects.create(
            survey=other, name="Other zones", geojson=geojson, feature_count=count,
            size_bytes=len(geojson),
        )
        other_question = Question.objects.create(
            survey_section=other_section, code="Q_OBJ", name="Routen",
            input_type="layer_objects", layer=other_layer,
        )

        purge_survey(self.survey)

        other_question.refresh_from_db()
        self.assertEqual(other_question.layer_id, other_layer.pk)
        self.assertTrue(SurveyMapLayer.objects.filter(pk=other_layer.pk).exists())

    def test_trash_row_names_the_layers_the_purge_will_destroy(self):
        """
        GIVEN a trashed survey owning one reference layer with one object
        WHEN the owner opens the dashboard
        THEN the Delete-forever row carries a note naming the layer and object counts
        """
        self.client.login(username='purgelayeruser', password='testpass123')
        self.client.post(f'/editor/delete/{self.survey.uuid}/')

        response = self.client.get('/editor/?dashboard=1')

        html = response.content.decode()
        self.assertIn('data-layer-note="Including 1 reference layer with 1 objects."', html)
        trashed = {s.pk: s for s in response.context['trashed_surveys']}
        self.assertEqual(trashed[self.survey.pk].layer_count, 1)
        self.assertEqual(trashed[self.survey.pk].layer_object_count, 1)

    def test_trash_row_without_layers_has_an_empty_note(self):
        """
        GIVEN a trashed survey owning no reference layers
        WHEN the owner opens the dashboard
        THEN its Delete-forever row carries no note, leaving the dialog as it was
        """
        bare = SurveyHeader.objects.create(
            name="bare_survey", organization=self.org, status='published',
        )
        self.client.login(username='purgelayeruser', password='testpass123')
        self.client.post(f'/editor/delete/{bare.uuid}/')

        response = self.client.get('/editor/?dashboard=1')

        html = response.content.decode()
        note = re.search(
            rf'data-survey-uuid="{bare.uuid}"\s+data-layer-note="([^"]*)"', html,
        )
        self.assertIsNotNone(note, "the Delete-forever button for the bare survey is missing")
        self.assertEqual(note.group(1), '')

    def test_purge_removes_layer_object_attachments_from_storage(self):
        """
        GIVEN a trashed survey whose layer object carries a file attachment
        WHEN the survey is purged
        THEN the file is removed from storage, not just its row
        """
        from django.core.files.base import ContentFile
        from survey.models import LayerObjectAsset
        from survey.trash import purge_survey

        gif = b'GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;'
        asset = LayerObjectAsset.objects.create(object=self.obj, kind='image')
        asset.file.save('purge_layer_asset.gif', ContentFile(gif), save=True)
        name, storage = asset.file.name, asset.file.storage
        self.assertTrue(storage.exists(name))

        purge_survey(self.survey)

        self.assertFalse(storage.exists(name))
        self.assertFalse(LayerObjectAsset.objects.filter(pk=asset.pk).exists())


class AutoPurgeCommandTest(TestCase):
    """Tests for the purge_trashed_surveys management command."""

    def setUp(self):
        """Set up one expired and one recent trashed survey."""
        from datetime import timedelta
        from django.utils import timezone
        self.org = _make_org('PurgeOrg')
        self.expired = SurveyHeader.objects.create(
            name="expired_survey", organization=self.org,
            deleted_at=timezone.now() - timedelta(days=31),
        )
        self.recent = SurveyHeader.objects.create(
            name="recent_survey", organization=self.org,
            deleted_at=timezone.now() - timedelta(days=5),
        )

    def test_purges_expired_keeps_recent(self):
        """
        GIVEN surveys trashed 31 and 5 days ago
        WHEN the purge command runs with the default 30-day window
        THEN the expired one is deleted with an auto-purge audit row and the recent one survives
        """
        from django.core.management import call_command
        from survey.models import AuditLog

        call_command('purge_trashed_surveys')

        self.assertFalse(SurveyHeader.objects.filter(pk=self.expired.pk).exists())
        self.assertTrue(SurveyHeader.objects.filter(pk=self.recent.pk).exists())
        entry = AuditLog.objects.get(action='survey_auto_purge', survey_uuid=self.expired.uuid)
        self.assertIsNone(entry.actor)
        self.assertEqual(entry.survey_name, 'expired_survey')

    def test_one_failing_survey_does_not_abandon_the_run(self):
        """
        GIVEN three expired surveys where purging the middle one raises
        WHEN the purge run executes
        THEN the other two are purged and the run reports one failure
        """
        from datetime import timedelta
        from unittest.mock import patch
        from django.utils import timezone
        from survey import trash as trash_module
        from survey.trash import purge_expired_surveys

        second = SurveyHeader.objects.create(
            name="expired_two", organization=self.org,
            deleted_at=timezone.now() - timedelta(days=32),
        )
        third = SurveyHeader.objects.create(
            name="expired_three", organization=self.org,
            deleted_at=timezone.now() - timedelta(days=33),
        )
        real_purge = trash_module.purge_survey

        def explode_on_second(survey):
            if survey.pk == second.pk:
                raise RuntimeError("boom")
            return real_purge(survey)

        with patch('survey.trash.purge_survey', side_effect=explode_on_second):
            run = purge_expired_surveys()

        self.assertEqual(run.purged, 2)
        self.assertEqual(run.failed, 1)
        self.assertTrue(SurveyHeader.objects.filter(pk=second.pk).exists())
        self.assertFalse(SurveyHeader.objects.filter(pk=self.expired.pk).exists())
        self.assertFalse(SurveyHeader.objects.filter(pk=third.pk).exists())

    def test_command_exits_non_zero_when_a_survey_fails(self):
        """
        GIVEN an expired survey whose purge raises
        WHEN the management command runs
        THEN it reports the failure as a command error rather than finishing quietly
        """
        from unittest.mock import patch
        from django.core.management import call_command
        from django.core.management.base import CommandError

        with patch('survey.trash.purge_survey', side_effect=RuntimeError("boom")):
            with self.assertRaises(CommandError):
                call_command('purge_trashed_surveys')

    def test_dry_run_touches_nothing(self):
        """
        GIVEN an expired trashed survey
        WHEN the purge command runs with --dry-run
        THEN nothing is deleted and no audit rows are written
        """
        from django.core.management import call_command
        from survey.models import AuditLog

        call_command('purge_trashed_surveys', '--dry-run')

        self.assertTrue(SurveyHeader.objects.filter(pk=self.expired.pk).exists())
        self.assertFalse(AuditLog.objects.filter(action='survey_auto_purge').exists())


class InternalPurgeEndpointTest(TestCase):
    """Tests for the token-gated /internal/purge-trash/ endpoint."""

    def setUp(self):
        """Set up an expired trashed survey."""
        from datetime import timedelta
        from django.utils import timezone
        self.org = _make_org('PurgeApiOrg')
        self.expired = SurveyHeader.objects.create(
            name="api_expired_survey", organization=self.org,
            deleted_at=timezone.now() - timedelta(days=31),
        )

    def test_valid_token_triggers_purge(self):
        """
        GIVEN PURGE_TASK_TOKEN is configured and a survey expired in trash
        WHEN POST arrives with the correct bearer token
        THEN the survey is purged and the count is returned
        """
        from django.test import override_settings
        from survey.models import AuditLog

        with override_settings(PURGE_TASK_TOKEN='testtoken123'):
            response = self.client.post(
                '/internal/purge-trash/', HTTP_AUTHORIZATION='Bearer testtoken123',
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'purged': 1, 'failed': 0})
        self.assertFalse(SurveyHeader.objects.filter(pk=self.expired.pk).exists())
        self.assertTrue(AuditLog.objects.filter(action='survey_auto_purge', survey_uuid=self.expired.uuid).exists())

    def test_wrong_or_missing_token_rejected(self):
        """
        GIVEN PURGE_TASK_TOKEN is configured
        WHEN POST arrives with a wrong token or none at all
        THEN 403 is returned and nothing is purged
        """
        from django.test import override_settings

        with override_settings(PURGE_TASK_TOKEN='testtoken123'):
            wrong = self.client.post('/internal/purge-trash/', HTTP_AUTHORIZATION='Bearer nope')
            missing = self.client.post('/internal/purge-trash/')

        self.assertEqual(wrong.status_code, 403)
        self.assertEqual(missing.status_code, 403)
        self.assertTrue(SurveyHeader.objects.filter(pk=self.expired.pk).exists())

    def test_endpoint_disabled_without_token_setting(self):
        """
        GIVEN PURGE_TASK_TOKEN is empty
        WHEN any POST arrives (even with an empty bearer)
        THEN 403 is returned
        """
        from django.test import override_settings

        with override_settings(PURGE_TASK_TOKEN=''):
            response = self.client.post('/internal/purge-trash/', HTTP_AUTHORIZATION='Bearer ')

        self.assertEqual(response.status_code, 403)
        self.assertTrue(SurveyHeader.objects.filter(pk=self.expired.pk).exists())

    def test_get_rejected(self):
        """
        GIVEN a configured token
        WHEN a GET request arrives
        THEN 405 is returned
        """
        from django.test import override_settings

        with override_settings(PURGE_TASK_TOKEN='testtoken123'):
            response = self.client.get('/internal/purge-trash/', HTTP_AUTHORIZATION='Bearer testtoken123')

        self.assertEqual(response.status_code, 405)
