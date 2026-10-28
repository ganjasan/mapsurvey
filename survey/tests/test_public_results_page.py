"""Tests for the `public-results-page` capability (openspec/specs/public-results-page/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase, Client, override_settings
from django.contrib.auth.models import User
from django.contrib.gis.geos import Point
import json
from survey.models import SurveyHeader, SurveySection, Question, SurveySession, Answer, Membership, PublicResultsPage, PublicResultsBlock
from django.db.utils import IntegrityError
from survey.tests.helpers import _make_org


class PublicResultsPageModelTest(TestCase):
    """Tests for the PublicResultsPage / PublicResultsBlock models."""

    def setUp(self):
        self.org = _make_org("PR Org")
        self.survey = SurveyHeader.objects.create(name="pr_survey", organization=self.org)

    def test_defaults(self):
        """
        GIVEN a survey
        WHEN a PublicResultsPage is created with only required fields
        THEN it defaults to k=3, mode=live, unpublished, public visibility
        """
        page = PublicResultsPage.objects.create(survey=self.survey, slug="pr-survey")
        self.assertEqual(page.k_anonymity_threshold, 3)
        self.assertEqual(page.mode, "live")
        self.assertFalse(page.is_published)
        self.assertEqual(page.visibility, "public")
        self.assertFalse(page.is_frozen())

    def test_slug_unique(self):
        """
        GIVEN an existing page with a slug
        WHEN creating another page with the same slug
        THEN an integrity error is raised
        """
        from django.db import IntegrityError
        PublicResultsPage.objects.create(survey=self.survey, slug="dup")
        other = SurveyHeader.objects.create(name="pr_survey2", organization=self.org)
        with self.assertRaises(IntegrityError):
            PublicResultsPage.objects.create(survey=other, slug="dup")

    def test_one_to_one_with_survey(self):
        """
        GIVEN a survey that already has a results page
        WHEN creating a second page for the same survey
        THEN an integrity error is raised (OneToOne)
        """
        from django.db import IntegrityError
        PublicResultsPage.objects.create(survey=self.survey, slug="pr-a")
        with self.assertRaises(IntegrityError):
            PublicResultsPage.objects.create(survey=self.survey, slug="pr-b")

    def test_blocks_cascade_on_page_delete(self):
        """
        GIVEN a page with blocks
        WHEN the page is deleted
        THEN its blocks are deleted too
        """
        page = PublicResultsPage.objects.create(survey=self.survey, slug="pr-cascade")
        PublicResultsBlock.objects.create(page=page, block_type="text", order=0)
        PublicResultsBlock.objects.create(page=page, block_type="text", order=1)
        self.assertEqual(PublicResultsBlock.objects.filter(page=page).count(), 2)
        page.delete()
        self.assertEqual(PublicResultsBlock.objects.count(), 0)

    def test_block_ordering(self):
        """
        GIVEN blocks created out of order
        WHEN querying the page's blocks
        THEN they are returned ordered by the order field
        """
        page = PublicResultsPage.objects.create(survey=self.survey, slug="pr-order")
        PublicResultsBlock.objects.create(page=page, block_type="text", order=2)
        PublicResultsBlock.objects.create(page=page, block_type="text", order=0)
        PublicResultsBlock.objects.create(page=page, block_type="chart", order=1)
        orders = list(page.blocks.values_list("order", flat=True))
        self.assertEqual(orders, [0, 1, 2])


class PublicResultsServiceTest(TestCase):
    """Tests for PublicResultsService aggregation and privacy guards."""

    def setUp(self):
        self.org = _make_org("PRS Org")
        self.survey = SurveyHeader.objects.create(
            name="prs_survey", organization=self.org, status="published",
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name="sec", code="S1", is_head=True,
        )
        self.choice_q = Question.objects.create(
            survey_section=self.section, code="Q_CH", name="Rate us",
            input_type="choice",
            choices=[{"code": 1, "name": "Yes"}, {"code": 2, "name": "No"}],
        )
        self.point_q = Question.objects.create(
            survey_section=self.section, code="Q_PT", name="Mark spot",
            input_type="point",
        )
        self.text_q = Question.objects.create(
            survey_section=self.section, code="Q_TX", name="Comment",
            input_type="text",
        )
        self.page = PublicResultsPage.objects.create(
            survey=self.survey, slug="prs", is_published=True,
        )

    def _session(self, survey=None, status="", deleted=False):
        return SurveySession.objects.create(
            survey=survey or self.survey, validation_status=status, is_deleted=deleted,
        )

    def _service(self):
        from survey.public_results import PublicResultsService
        return PublicResultsService(self.page)

    def test_clean_excludes_deleted_and_not_approved(self):
        """
        GIVEN clean, deleted, and not_approved sessions
        WHEN response_count is computed
        THEN only the clean session is counted
        """
        self._session()                              # clean
        self._session(deleted=True)                  # deleted
        self._session(status="not_approved")         # junk
        self._session(status="on_hold")              # disputed
        self.assertEqual(self._service().response_count(), 1)

    def test_canonical_span(self):
        """
        GIVEN a canonical survey with a version copy, each with a clean session
        WHEN response_count is computed for the canonical page
        THEN sessions from both surveys are counted
        """
        version = SurveyHeader.objects.create(
            name="prs_v0", organization=self.org, is_canonical=False,
            canonical_survey=self.survey, version_number=1,
        )
        self._session()                       # canonical
        self._session(survey=version)         # version copy
        self.assertEqual(self._service().response_count(), 2)

    def test_k_anonymity_masks_small_bucket(self):
        """
        GIVEN a choice with a 2-vote option and a 4-vote option (K=3)
        WHEN the chart block is built
        THEN the small option shows "<3" with no value and the large is exact
        """
        for _ in range(2):
            s = self._session()
            Answer.objects.create(survey_session=s, question=self.choice_q, selected_choices=[1])
        for _ in range(4):
            s = self._session()
            Answer.objects.create(survey_session=s, question=self.choice_q, selected_choices=[2])
        block = PublicResultsBlock.objects.create(
            page=self.page, block_type="chart", question=self.choice_q, order=0,
        )
        payload = self._service()._build_block(block)
        by_code = {i["code"]: i for i in payload["items"]}
        self.assertTrue(by_code[1]["masked"])
        self.assertEqual(by_code[1]["display"], "<3")
        self.assertIsNone(by_code[1]["value"])
        self.assertFalse(by_code[2]["masked"])
        self.assertEqual(by_code[2]["display"], "4")

    def test_geo_has_no_record_identifiers(self):
        """
        GIVEN point answers and a map block with no popup fields selected
        WHEN the map payload is built
        THEN features carry empty properties and no session id is exposed
        """
        for _ in range(2):
            s = self._session()
            Answer.objects.create(survey_session=s, question=self.point_q, point=Point(30.0, 59.0))
        block = PublicResultsBlock.objects.create(
            page=self.page, block_type="map", question=self.point_q, order=0,
        )
        payload = self._service()._build_block(block)
        self.assertEqual(payload["count"], 2)
        for feat in payload["feature_collection"]["features"]:
            self.assertEqual(feat["properties"], {})
        self.assertNotIn("session_id", json.dumps(payload))

    def test_geo_popup_uses_point_subanswers(self):
        """
        GIVEN a map block whose geo question has a choice sub-question selected
        WHEN the map payload is built
        THEN each point's popup shows that point's own sub-answer, and free-text
             sub-answers never appear
        """
        # Sub-questions of the point question (attributes of each point)
        sub_choice = Question.objects.create(
            survey_section=self.section, code="SQ_ACT", name="Activity",
            input_type="choice", parent_question_id=self.point_q,
            choices=[{"code": 1, "name": "Walking"}, {"code": 2, "name": "Cycling"}],
        )
        sub_text = Question.objects.create(
            survey_section=self.section, code="SQ_TX", name="Note",
            input_type="text", parent_question_id=self.point_q,
        )
        s = self._session()
        pt = Answer.objects.create(survey_session=s, question=self.point_q, point=Point(30.0, 59.0))
        Answer.objects.create(survey_session=s, question=sub_choice, selected_choices=[1], parent_answer_id=pt)
        Answer.objects.create(survey_session=s, question=sub_text, text="secret", parent_answer_id=pt)
        block = PublicResultsBlock.objects.create(
            page=self.page, block_type="map", question=self.point_q, order=0,
            geo_label_fields=["SQ_ACT"],
        )
        payload = self._service()._build_block(block)
        props = payload["feature_collection"]["features"][0]["properties"]
        self.assertEqual(props, {"Activity": "Walking"})
        self.assertNotIn("secret", json.dumps(payload))

    def test_geo_popup_is_per_point_not_per_session(self):
        """
        GIVEN one respondent who marks two points with different sub-answers
        WHEN the map payload is built
        THEN each point's popup shows its own value (proves per-point join)
        """
        sub_choice = Question.objects.create(
            survey_section=self.section, code="SQ_ACT", name="Activity",
            input_type="choice", parent_question_id=self.point_q,
            choices=[{"code": 1, "name": "Walking"}, {"code": 2, "name": "Cycling"}],
        )
        s = self._session()
        p1 = Answer.objects.create(survey_session=s, question=self.point_q, point=Point(30.0, 59.0))
        p2 = Answer.objects.create(survey_session=s, question=self.point_q, point=Point(31.0, 60.0))
        Answer.objects.create(survey_session=s, question=sub_choice, selected_choices=[1], parent_answer_id=p1)
        Answer.objects.create(survey_session=s, question=sub_choice, selected_choices=[2], parent_answer_id=p2)
        block = PublicResultsBlock.objects.create(
            page=self.page, block_type="map", question=self.point_q, order=0,
            geo_label_fields=["SQ_ACT"],
        )
        payload = self._service()._build_block(block)
        values = sorted(
            f["properties"].get("Activity")
            for f in payload["feature_collection"]["features"]
        )
        self.assertEqual(values, ["Cycling", "Walking"])

    def test_map_payload_includes_basemap(self):
        """
        GIVEN a map block with a chosen basemap
        WHEN the map payload is built
        THEN the payload carries that basemap so the client picks the tile layer
        """
        s = self._session()
        Answer.objects.create(survey_session=s, question=self.point_q, point=Point(30.0, 59.0))
        block = PublicResultsBlock.objects.create(
            page=self.page, block_type="map", question=self.point_q, order=0, basemap="satellite",
        )
        payload = self._service()._build_block(block)
        self.assertEqual(payload["basemap"], "satellite")

    def test_map_block_defaults_to_streets_basemap(self):
        """
        GIVEN a map block created without specifying a basemap
        WHEN the payload is built
        THEN it defaults to the streets basemap
        """
        s = self._session()
        Answer.objects.create(survey_session=s, question=self.point_q, point=Point(30.0, 59.0))
        block = PublicResultsBlock.objects.create(
            page=self.page, block_type="map", question=self.point_q, order=0,
        )
        self.assertEqual(self._service()._build_block(block)["basemap"], "streets")

    def test_deleted_question_block_omitted(self):
        """
        GIVEN a chart block whose question was deleted (FK set to null)
        WHEN blocks are built
        THEN that block is silently omitted
        """
        block = PublicResultsBlock.objects.create(
            page=self.page, block_type="chart", question=self.choice_q, order=0,
        )
        block.question = None
        block.save()
        self.assertEqual(self._service().build_blocks(), [])

    def test_text_question_not_chartable(self):
        """
        GIVEN a chart block defensively bound to a text question
        WHEN the block is built
        THEN it produces no payload
        """
        block = PublicResultsBlock.objects.create(
            page=self.page, block_type="chart", question=self.text_q, order=0,
        )
        self.assertIsNone(self._service()._build_block(block))

    def test_zero_responses_count(self):
        """
        GIVEN a page with no clean responses
        WHEN the response count is computed
        THEN it is zero
        """
        self.assertEqual(self._service().response_count(), 0)

    def test_image_block_without_file_produces_no_payload(self):
        """
        GIVEN an image block with no file attached
        WHEN the block is built
        THEN it produces no payload (defensive, mirrors deleted-question blocks)
        """
        block = PublicResultsBlock.objects.create(
            page=self.page, block_type="image", order=0,
        )
        self.assertIsNone(self._service()._build_block(block))

    def test_image_block_payload_includes_url_and_caption(self):
        """
        GIVEN an image block with a file and a caption
        WHEN the block is built
        THEN the payload carries the image URL and localized caption
        """
        from django.core.files.uploadedfile import SimpleUploadedFile
        gif_bytes = (
            b'GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!\xf9\x04'
            b'\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;'
        )
        block = PublicResultsBlock.objects.create(
            page=self.page, block_type="image", order=0,
            image=SimpleUploadedFile("pic.gif", gif_bytes, content_type="image/gif"),
            content={"en": "A lovely spot"},
        )
        payload = self._service()._build_block(block)
        self.assertIn("pic", payload["image_url"])
        self.assertEqual(payload["caption"], "A lovely spot")


class PublicResultsFreezeTest(TestCase):
    """Tests for freeze/live mechanics of the public results page."""

    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.org = _make_org("PRF Org")
        self.survey = SurveyHeader.objects.create(
            name="prf_survey", organization=self.org, status="published",
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name="sec", code="S1", is_head=True,
        )
        self.page = PublicResultsPage.objects.create(
            survey=self.survey, slug="prf", is_published=True,
        )

    def _add_session(self):
        SurveySession.objects.create(survey=self.survey)

    def test_freeze_captures_current_data(self):
        """
        GIVEN a page with 2 clean responses
        WHEN it is frozen
        THEN the snapshot records the count and the page switches to frozen
        """
        from survey.public_results import freeze_page
        self._add_session(); self._add_session()
        freeze_page(self.page)
        self.assertEqual(self.page.mode, "frozen")
        self.assertIsNotNone(self.page.frozen_at)
        self.assertEqual(self.page.snapshot["response_count"], 2)

    def test_frozen_does_not_change(self):
        """
        GIVEN a frozen page
        WHEN a new response arrives
        THEN the rendered count stays equal to the snapshot
        """
        from survey.public_results import freeze_page, render_page_data
        self._add_session()
        freeze_page(self.page)
        self._add_session()
        data = render_page_data(self.page)
        self.assertTrue(data["frozen"])
        self.assertEqual(data["response_count"], 1)

    def test_live_reflects_new_response_after_cache_clear(self):
        """
        GIVEN a live page rendered once
        WHEN a new response arrives and the cache window passes
        THEN the rendered count increases
        """
        from django.core.cache import cache
        from survey.public_results import render_page_data
        self._add_session()
        self.assertEqual(render_page_data(self.page)["response_count"], 1)
        self._add_session()
        cache.clear()  # simulate TTL expiry
        self.assertEqual(render_page_data(self.page)["response_count"], 2)

    def test_live_is_cached_within_window(self):
        """
        GIVEN a live page rendered once
        WHEN a new response arrives but the cache is still warm
        THEN the rendered count is unchanged until the cache expires
        """
        from survey.public_results import render_page_data
        self._add_session()
        self.assertEqual(render_page_data(self.page)["response_count"], 1)
        self._add_session()
        self.assertEqual(render_page_data(self.page)["response_count"], 1)

    def test_block_deletion_bypasses_live_cache(self):
        """
        GIVEN a live page primed into the cache with two blocks
        WHEN a block is deleted and the page version is bumped
        THEN the next render reflects one block, without clearing the cache manually
        """
        from survey.public_results import render_page_data, bump_page_version
        PublicResultsBlock.objects.create(page=self.page, block_type="text", order=0)
        b2 = PublicResultsBlock.objects.create(page=self.page, block_type="text", order=1)
        self.assertEqual(len(render_page_data(self.page)["blocks"]), 2)  # prime cache
        b2.delete()
        bump_page_version(self.page)
        self.page.refresh_from_db()
        self.assertEqual(len(render_page_data(self.page)["blocks"]), 1)

    def test_new_response_still_cached_with_versioned_key(self):
        """
        GIVEN a live page primed into the cache
        WHEN a new response arrives but no configuration change bumps the version
        THEN the cached render is unchanged within the window
              (config invalidation does not defeat data caching)
        """
        from survey.public_results import render_page_data
        self._add_session()
        self.assertEqual(render_page_data(self.page)["response_count"], 1)
        self._add_session()  # arrives within the TTL window, no version bump
        self.assertEqual(render_page_data(self.page)["response_count"], 1)

    def test_return_to_live_recomputes(self):
        """
        GIVEN a frozen page returned to live
        WHEN a new response arrives
        THEN the rendered count reflects current data
        """
        from django.core.cache import cache
        from survey.public_results import freeze_page, unfreeze_page, render_page_data
        self._add_session()
        freeze_page(self.page)
        unfreeze_page(self.page)
        self._add_session()
        cache.clear()
        data = render_page_data(self.page)
        self.assertFalse(data["frozen"])
        self.assertEqual(data["response_count"], 2)

    def test_stale_snapshot_version(self):
        """
        GIVEN a frozen page whose snapshot uses an incompatible version
        WHEN it is rendered
        THEN it is flagged stale rather than rendering wrong data
        """
        from survey.public_results import render_page_data
        self.page.mode = "frozen"
        self.page.snapshot = {"snapshot_version": 999, "response_count": 5, "blocks": []}
        self.page.save()
        data = render_page_data(self.page)
        self.assertTrue(data["stale"])
        self.assertEqual(data["blocks"], [])


class PublicResultsViewTest(TestCase):
    """Tests for the public /r/<slug>/ view and SEO behavior."""

    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.client = Client()
        self.org = _make_org("PRV Org")
        self.survey = SurveyHeader.objects.create(
            name="prv_survey", organization=self.org, status="published",
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name="sec", code="S1", is_head=True,
        )
        self.choice_q = Question.objects.create(
            survey_section=self.section, code="Q_CH", name="Rate", input_type="choice",
            choices=[{"code": 1, "name": "Yes"}, {"code": 2, "name": "No"}],
        )
        self.text_q = Question.objects.create(
            survey_section=self.section, code="Q_TX", name="Comment", input_type="text",
        )
        self.page = PublicResultsPage.objects.create(
            survey=self.survey, slug="prv", is_published=True, visibility="public",
            intro={"title": {"en": "Park results"}, "body": {"en": "Thanks all"}},
        )
        PublicResultsBlock.objects.create(page=self.page, block_type="text", order=0)
        PublicResultsBlock.objects.create(
            page=self.page, block_type="chart", question=self.choice_q, order=1,
        )

    def test_chart_block_viz_delivered_to_client(self):
        """
        GIVEN a chart block whose visualization is set to pie
        WHEN the public page is rendered
        THEN the block payload delivered to the client carries viz=pie
              so the chart renderer can honor the selected visualization
        """
        block = PublicResultsBlock.objects.get(page=self.page, block_type="chart")
        block.viz = "pie"
        block.save()
        r = self.client.get("/r/{}/".format(self.page.slug))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, '"viz": "pie"')

    def test_public_page_uses_no_volunteer_tile_servers(self):
        """
        GIVEN a published public results page
        WHEN anyone loads /r/<slug>/
        THEN it requests tiles from neither OSM's nor OpenTopoMap's volunteer servers,
              and the basemap URLs come from the Mapbox settings like every other map

        This page used to hard-code tile.openstreetmap.org, a tile usage policy
        violation on a page creators are asked to publish and promote.
        """
        r = self.client.get("/r/{}/".format(self.page.slug))
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, "tile.openstreetmap.org")
        self.assertNotContains(r, "tile.opentopomap.org")
        self.assertContains(r, "mapbox/outdoors-v12")

    def test_kanon_note_conditional_on_threshold(self):
        """
        GIVEN a page with masking enabled (k=3) and one with it disabled (k=1)
        WHEN the public page renders a chart block
        THEN the masking note shows only while masking is enabled
        """
        r = self.client.get("/r/{}/".format(self.page.slug))
        self.assertContains(r, "Small groups are masked")
        self.page.k_anonymity_threshold = 1
        self.page.save()
        from survey.public_results import bump_page_version
        bump_page_version(self.page)
        r = self.client.get("/r/{}/".format(self.page.slug))
        self.assertNotContains(r, "Small groups are masked")

    def test_image_block_renders_on_public_page(self):
        """
        GIVEN an image block with a caption
        WHEN the public page is rendered
        THEN the image tag and caption appear
        """
        from django.core.files.uploadedfile import SimpleUploadedFile
        gif_bytes = (
            b'GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!\xf9\x04'
            b'\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;'
        )
        PublicResultsBlock.objects.create(
            page=self.page, block_type="image", order=2,
            image=SimpleUploadedFile("pic.gif", gif_bytes, content_type="image/gif"),
            content={"en": "A lovely spot"},
        )
        r = self.client.get("/r/{}/".format(self.page.slug))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "<img src=")
        self.assertContains(r, "A lovely spot")

    def test_published_page_reachable(self):
        """
        GIVEN a published public results page
        WHEN an anonymous visitor opens /r/<slug>/
        THEN it returns 200 with the intro title and platform footer
        """
        r = self.client.get("/r/prv/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Park results")
        self.assertContains(r, "Made with")

    def test_unpublished_page_404(self):
        """
        GIVEN an unpublished page
        WHEN opened
        THEN 404
        """
        self.page.is_published = False
        self.page.save()
        self.assertEqual(self.client.get("/r/prv/").status_code, 404)

    def test_unknown_slug_404(self):
        """
        GIVEN no page with the slug
        WHEN opened
        THEN 404
        """
        self.assertEqual(self.client.get("/r/nope/").status_code, 404)

    def test_public_is_indexable(self):
        """
        GIVEN a public page
        WHEN rendered
        THEN it allows indexing and appears in the sitemap
        """
        r = self.client.get("/r/prv/")
        self.assertContains(r, "index, follow")
        sitemap = self.client.get("/sitemap.xml")
        self.assertContains(sitemap, "/r/prv/")

    def test_unlisted_is_noindex_and_absent_from_sitemap(self):
        """
        GIVEN an unlisted page
        WHEN rendered
        THEN it emits noindex and is excluded from the sitemap
        """
        self.page.visibility = "unlisted"
        self.page.save()
        r = self.client.get("/r/prv/")
        self.assertContains(r, "noindex")
        sitemap = self.client.get("/sitemap.xml")
        self.assertNotContains(sitemap, "/r/prv/")

    def test_cta_visible_when_survey_open(self):
        """
        GIVEN an open survey with the CTA enabled
        WHEN the page is rendered
        THEN the "Take the survey" action is shown
        """
        r = self.client.get("/r/prv/")
        self.assertContains(r, "Take the survey")

    def test_cta_hidden_when_survey_closed(self):
        """
        GIVEN a closed survey
        WHEN the page is rendered
        THEN the CTA is not shown
        """
        self.survey.status = "closed"
        self.survey.save()
        r = self.client.get("/r/prv/")
        self.assertNotContains(r, "Take the survey")

    def test_no_raw_text_answers_on_page(self):
        """
        GIVEN a session with a free-text answer
        WHEN the public page is rendered
        THEN the individual text never appears in the response
        """
        s = SurveySession.objects.create(survey=self.survey)
        Answer.objects.create(survey_session=s, question=self.text_q, text="topsecretcomment")
        Answer.objects.create(survey_session=s, question=self.choice_q, selected_choices=[1])
        r = self.client.get("/r/prv/")
        self.assertNotContains(r, "topsecretcomment")


class PublicResultsEditorTest(TestCase):
    """Tests for the editor configuration views of the public results page."""

    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.client = Client()
        self.org = _make_org("PRE Org")
        self.user = User.objects.create_user(username="prowner", password="pw12345")
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.survey = SurveyHeader.objects.create(
            name="pre_survey", organization=self.org, status="published",
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name="sec", code="S1", is_head=True,
        )
        self.choice_q = Question.objects.create(
            survey_section=self.section, code="Q_CH", name="Rate", input_type="choice",
            choices=[{"code": 1, "name": "Yes"}],
        )
        self.text_q = Question.objects.create(
            survey_section=self.section, code="Q_TX", name="Comment", input_type="text",
        )
        self.point_q = Question.objects.create(
            survey_section=self.section, code="Q_PT", name="Mark spot", input_type="point",
        )
        self.base = "/editor/surveys/{}/public-results/".format(self.survey.uuid)

    def _login(self):
        self.client.login(username="prowner", password="pw12345")

    def test_config_lazily_creates_page(self):
        """
        GIVEN no results page yet
        WHEN the editor opens the config tab
        THEN a page is created and the tab renders
        """
        self._login()
        r = self.client.get(self.base)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(PublicResultsPage.objects.filter(survey=self.survey).exists())

    def test_k_anonymity_help_escapes_less_than(self):
        """
        GIVEN the page settings card with the k-anonymity help text "Mask buckets smaller than K as “<K”"
        WHEN the editor opens the config tab
        THEN "<K" reaches the browser escaped, so it cannot open a tag that swallows the closing
             </div> and pull the Data mode card and the live preview into the settings card
        """
        self._login()
        r = self.client.get(self.base)
        html = r.content.decode()
        self.assertIn("“&lt;K”", html)
        self.assertNotIn("“<K”", html)

    def test_non_editor_blocked(self):
        """
        GIVEN a user without rights on the survey
        WHEN they request the config tab
        THEN access is denied and no page is created
        """
        User.objects.create_user(username="outsider", password="pw12345")
        self.client.login(username="outsider", password="pw12345")
        r = self.client.get(self.base)
        self.assertIn(r.status_code, (302, 403, 404))
        self.assertFalse(PublicResultsPage.objects.filter(survey=self.survey).exists())

    def test_add_question_block(self):
        """
        GIVEN a choice question
        WHEN it is added as a block
        THEN a chart block is created and the editor lands in its config
        """
        self._login()
        r = self.client.post(self.base + "blocks/add/", {
            "block_type": "question", "question_id": self.choice_q.id,
        })
        block = PublicResultsBlock.objects.get(page__survey=self.survey)
        self.assertEqual(block.block_type, "chart")
        self.assertEqual(block.question_id, self.choice_q.id)
        # P3: redirect selects the freshly created block
        self.assertEqual(r.status_code, 302)
        self.assertIn(f"?block={block.id}", r.url)

    @override_settings(MOBILE_EDITOR_NAV=False)
    def test_settings_preview_button_works_before_page_is_live(self):
        """
        GIVEN a results page that is not yet published
        WHEN the config tab renders
        THEN the Preview button targets the always-available editor preview
             endpoint (the public /r/ URL would 404), and the "Live page"
             link appears only once the page is published
        """
        self._login()
        r = self.client.get(self.base)
        content = r.content.decode()
        self.assertIn(f"{self.base}preview/", content)
        self.assertNotIn("Live page", content)
        page = PublicResultsPage.objects.get(survey=self.survey)
        page.is_published = True
        page.save()
        content = self.client.get(self.base).content.decode()
        self.assertIn("Live page", content)

    def test_text_question_not_addable(self):
        """
        GIVEN a text question
        WHEN an attempt is made to add it as a block
        THEN the request is rejected and no block is created
        """
        self._login()
        r = self.client.post(self.base + "blocks/add/", {
            "block_type": "question", "question_id": self.text_q.id,
        })
        self.assertEqual(r.status_code, 400)
        self.assertFalse(PublicResultsBlock.objects.exists())

    def _gif_upload(self, name="pic.gif"):
        from django.core.files.uploadedfile import SimpleUploadedFile
        gif_bytes = (
            b'GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!\xf9\x04'
            b'\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;'
        )
        return SimpleUploadedFile(name, gif_bytes, content_type="image/gif")

    def test_add_image_block(self):
        """
        GIVEN an uploaded image file
        WHEN it is added as an image block
        THEN an image block is created with the file attached
        """
        self._login()
        self.client.post(self.base + "blocks/add/", {
            "block_type": "image", "image": self._gif_upload(),
        })
        block = PublicResultsBlock.objects.get(page__survey=self.survey)
        self.assertEqual(block.block_type, "image")
        self.assertTrue(block.image)

    def test_add_image_block_without_file_rejected(self):
        """
        GIVEN no file attached
        WHEN an attempt is made to add an image block
        THEN the request is rejected and no block is created
        """
        self._login()
        r = self.client.post(self.base + "blocks/add/", {"block_type": "image"})
        self.assertEqual(r.status_code, 400)
        self.assertFalse(PublicResultsBlock.objects.exists())

    def test_edit_image_block_caption_and_replace(self):
        """
        GIVEN an existing image block
        WHEN its caption is updated and the file is replaced
        THEN both changes persist
        """
        self._login()
        page = self.client.get(self.base) and PublicResultsPage.objects.get(survey=self.survey)
        block = PublicResultsBlock.objects.create(
            page=page, block_type="image", image=self._gif_upload("old.gif"), order=0,
        )
        old_name = block.image.name
        self.client.post(self.base + "blocks/{}/edit/".format(block.id), {
            "content": "Updated caption", "image": self._gif_upload("new.gif"),
        })
        block.refresh_from_db()
        self.assertEqual(block.content["en"], "Updated caption")
        self.assertNotEqual(block.image.name, old_name)

    def test_counter_block_type_rejected(self):
        """
        GIVEN the retired 'counter' block type (duplicated the page-level
              response counter shown in the hero)
        WHEN an attempt is made to add one
        THEN the request is rejected and no block is created
        """
        self._login()
        r = self.client.post(self.base + "blocks/add/", {"block_type": "counter"})
        self.assertEqual(r.status_code, 400)
        self.assertFalse(PublicResultsBlock.objects.exists())

    def test_reorder_persists(self):
        """
        GIVEN three blocks
        WHEN a new order is posted
        THEN the stored order matches
        """
        self._login()
        page = self.client.get(self.base) and PublicResultsPage.objects.get(survey=self.survey)
        b1 = PublicResultsBlock.objects.create(page=page, block_type="text", order=0)
        b2 = PublicResultsBlock.objects.create(page=page, block_type="text", order=1)
        b3 = PublicResultsBlock.objects.create(page=page, block_type="text", order=2)
        self.client.post(
            self.base + "blocks/reorder/",
            data=json.dumps({"order": [b3.id, b1.id, b2.id]}),
            content_type="application/json",
        )
        self.assertEqual(PublicResultsBlock.objects.get(id=b3.id).order, 0)
        self.assertEqual(PublicResultsBlock.objects.get(id=b1.id).order, 1)
        self.assertEqual(PublicResultsBlock.objects.get(id=b2.id).order, 2)

    def test_delete_block_reflected_in_live_render_immediately(self):
        """
        GIVEN a live page whose cache is primed with one block
        WHEN the editor deletes the block via the view
        THEN the next public render shows zero blocks, without manual cache clearing
        """
        from survey.public_results import render_page_data
        self._login()
        # Create the page directly: opening the config tab of this published
        # survey would auto-scaffold question blocks and skew the count.
        page = PublicResultsPage.objects.create(survey=self.survey, slug="pre-live")
        block = PublicResultsBlock.objects.create(page=page, block_type="text", order=0)
        self.assertEqual(len(render_page_data(page)["blocks"]), 1)  # prime cache
        self.client.post(self.base + "blocks/{}/delete/".format(block.id))
        page.refresh_from_db()
        self.assertEqual(len(render_page_data(page)["blocks"]), 0)

    def test_freeze_and_unfreeze(self):
        """
        GIVEN a live page
        WHEN freeze then unfreeze are posted
        THEN the mode toggles accordingly
        """
        self._login()
        self.client.get(self.base)
        self.client.post(self.base + "freeze/")
        self.assertEqual(PublicResultsPage.objects.get(survey=self.survey).mode, "frozen")
        self.client.post(self.base + "unfreeze/")
        self.assertEqual(PublicResultsPage.objects.get(survey=self.survey).mode, "live")

    def test_publish_action_toggles_live_state(self):
        """
        GIVEN a page and the explicit publish endpoint
        WHEN publish=1 then publish=0 are posted
        THEN is_published flips accordingly
        """
        self._login()
        self.client.get(self.base)
        r = self.client.post(self.base + "set-published/", {"publish": "1"}, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["is_published"])
        self.assertTrue(PublicResultsPage.objects.get(survey=self.survey).is_published)
        self.client.post(self.base + "set-published/", {"publish": "0"}, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertFalse(PublicResultsPage.objects.get(survey=self.survey).is_published)

    def test_publish_action_blocked_on_draft_survey(self):
        """
        GIVEN a draft survey
        WHEN the results page publish action is invoked
        THEN it is refused and the page stays unpublished
        """
        self.survey.status = "draft"
        self.survey.save()
        self._login()
        self.client.get(self.base)
        r = self.client.post(self.base + "set-published/", {"publish": "1"}, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(r.status_code, 400)
        self.assertFalse(PublicResultsPage.objects.get(survey=self.survey).is_published)

    def test_settings_autosave_does_not_unpublish(self):
        """
        GIVEN a live results page
        WHEN a settings autosave omits is_published (the checkbox is gone)
        THEN the page stays live
        """
        self._login()
        page = self.client.get(self.base) and PublicResultsPage.objects.get(survey=self.survey)
        page.is_published = True
        page.save()
        self.client.post(
            self.base + "settings/",
            {"visibility": "public", "k_anonymity_threshold": "3", "intro_title": "Hi"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        page.refresh_from_db()
        self.assertTrue(page.is_published)

    def test_draft_survey_cannot_publish(self):
        """
        GIVEN a draft survey
        WHEN settings are saved with publish on
        THEN the page stays unpublished
        """
        self.survey.status = "draft"
        self.survey.save()
        self._login()
        self.client.get(self.base)
        self.client.post(self.base + "settings/", {
            "visibility": "public", "is_published": "on", "slug": "pre",
            "k_anonymity_threshold": "3",
        })
        self.assertFalse(PublicResultsPage.objects.get(survey=self.survey).is_published)

    def test_save_settings_persists(self):
        """
        GIVEN a published survey
        WHEN settings are saved
        THEN visibility, k-threshold, and intro persist
        """
        self._login()
        self.client.get(self.base)
        self.client.post(self.base + "settings/", {
            "visibility": "unlisted", "is_published": "on", "slug": "pre-x",
            "intro_title": "Hello", "intro_body": "World",
            "show_response_count": "on", "k_anonymity_threshold": "5",
        })
        page = PublicResultsPage.objects.get(survey=self.survey)
        self.assertEqual(page.visibility, "unlisted")
        self.assertTrue(page.is_published)
        self.assertEqual(page.k_anonymity_threshold, 5)
        self.assertEqual(page.intro["title"]["en"], "Hello")
        self.assertEqual(page.slug, "pre-x")

    def test_settings_autosave_ajax_returns_json(self):
        """
        GIVEN the page settings form is submitted via XHR (autosave)
        WHEN the request carries X-Requested-With and omits the slug
        THEN a JSON ok response is returned (no redirect), values persist,
              and the existing slug is preserved
        """
        self._login()
        self.client.get(self.base)
        page = PublicResultsPage.objects.get(survey=self.survey)
        original_slug = page.slug
        r = self.client.post(
            self.base + "settings/",
            {"visibility": "unlisted", "k_anonymity_threshold": "4", "intro_title": "Hi"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["ok"])
        page.refresh_from_db()
        self.assertEqual(page.visibility, "unlisted")
        self.assertEqual(page.k_anonymity_threshold, 4)
        self.assertEqual(page.slug, original_slug)

    def test_slug_apply_reports_taken(self):
        """
        GIVEN another page already owns a slug
        WHEN the creator applies that slug via XHR
        THEN the response flags slug_taken and the slug is unchanged
        """
        self._login()
        self.client.get(self.base)
        page = PublicResultsPage.objects.get(survey=self.survey)
        original_slug = page.slug
        other = SurveyHeader.objects.create(
            name="other_pre", organization=self.org, status="published",
        )
        PublicResultsPage.objects.create(survey=other, slug="taken-slug", is_published=True)
        r = self.client.post(
            self.base + "settings/",
            {"visibility": page.visibility, "k_anonymity_threshold": "3", "slug": "taken-slug"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["slug_taken"])
        page.refresh_from_db()
        self.assertEqual(page.slug, original_slug)

    def test_block_edit_autosave_ajax_returns_json(self):
        """
        GIVEN a chart block
        WHEN its visualization is changed via XHR (autosave)
        THEN a JSON ok response is returned and the new viz persists
        """
        self._login()
        page = self.client.get(self.base) and PublicResultsPage.objects.get(survey=self.survey)
        block = PublicResultsBlock.objects.create(
            page=page, block_type="chart", question=self.choice_q, order=0,
        )
        r = self.client.post(
            self.base + "blocks/{}/edit/".format(block.id),
            {"viz": "pie"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["ok"])
        block.refresh_from_db()
        self.assertEqual(block.viz, "pie")

    def test_map_block_basemap_saved(self):
        """
        GIVEN a map block
        WHEN a valid basemap is submitted
        THEN it persists; an invalid value is ignored (keeps the previous one)
        """
        self._login()
        page = self.client.get(self.base) and PublicResultsPage.objects.get(survey=self.survey)
        block = PublicResultsBlock.objects.create(
            page=page, block_type="map", question=self.point_q, order=0,
        )
        self.client.post(self.base + "blocks/{}/edit/".format(block.id), {"viz": "heatmap", "basemap": "topo"})
        block.refresh_from_db()
        self.assertEqual(block.basemap, "topo")
        # An invalid basemap must not overwrite the stored value.
        self.client.post(self.base + "blocks/{}/edit/".format(block.id), {"viz": "heatmap", "basemap": "bogus"})
        block.refresh_from_db()
        self.assertEqual(block.basemap, "topo")


class PublicResultsPreviewTest(TestCase):
    """Tests for the editor preview endpoint (iframe source)."""

    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.client = Client()
        self.org = _make_org("PRP Org")
        self.user = User.objects.create_user(username="prpowner", password="pw12345")
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.survey = SurveyHeader.objects.create(
            name="prp_survey", organization=self.org, status="published",
        )
        SurveySection.objects.create(survey_header=self.survey, name="s", code="S1", is_head=True)
        self.base = "/editor/surveys/{}/public-results/".format(self.survey.uuid)

    def test_preview_renders_for_editor_even_if_unpublished(self):
        """
        GIVEN an unpublished results page
        WHEN the editor opens the preview endpoint
        THEN it renders the public template (200) with same-origin framing and noindex
        """
        self.client.login(username="prpowner", password="pw12345")
        r = self.client.get(self.base + "preview/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Made with")
        self.assertContains(r, "noindex")
        self.assertEqual(r.headers.get("X-Frame-Options"), "SAMEORIGIN")

    def test_preview_requires_editor(self):
        """
        GIVEN a user without rights
        WHEN they request the preview endpoint
        THEN access is denied
        """
        User.objects.create_user(username="prpoutsider", password="pw12345")
        self.client.login(username="prpoutsider", password="pw12345")
        r = self.client.get(self.base + "preview/")
        self.assertIn(r.status_code, (302, 403, 404))
