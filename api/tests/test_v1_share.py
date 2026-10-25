"""`rest-api-v1` (change api-v2-distribution, #410): share information, QR,
tracked links, embed hosts -- and the Share page's own links."""
from django.test import TestCase, override_settings

from survey.models import AuditLog, SurveyEvent, SurveySession, TrackedLink

from .helpers import LOCMEM, V1Client, make_member, make_pro_org, make_v1_survey, mint

SITE = 'https://mapsurvey.example'


@LOCMEM
@override_settings(SITE_URL=SITE)
class ShareApiTest(TestCase):
    def setUp(self):
        self.org, self.owner = make_pro_org()
        self.survey, self.section = make_v1_survey(self.org, self.owner, status='published')
        self.api = V1Client(self.client, mint(self.owner)[0])
        self.base = f'/surveys/{self.survey.uuid}'

    # ── share information ──

    def test_published_survey_share_info(self):
        """
        GIVEN a published survey and a viewer
        WHEN the viewer asks for its share information
        THEN it is shareable, with the SITE_URL link, the embed snippet and no test link
        """
        viewer = make_member(self.org, 'share_viewer', role='viewer')
        data = self.api.get(f'{self.base}/share', token=mint(viewer)[0]).json()
        self.assertTrue(data['shareable'])
        self.assertEqual(data['url'], f'{SITE}/surveys/{self.survey.uuid}/')
        self.assertIn(f'src="{SITE}/surveys/{self.survey.uuid}/?embed=1"', data['embed_snippet'])
        self.assertIn(f'{SITE}/embed.js', data['embed_snippet'])
        self.assertIsNone(data['test_url'])

    def test_testing_survey_test_link_only_for_editors(self):
        """
        GIVEN a survey in testing
        WHEN the owner and a viewer ask
        THEN the owner gets the test link with its token, the viewer none, and neither a share link
        """
        self.survey.status = 'testing'
        self.survey.save()
        owner = self.api.get(f'{self.base}/share').json()
        self.assertFalse(owner['shareable'])
        self.assertIsNone(owner['url'])
        self.assertEqual(owner['test_url'], f'{SITE}/surveys/{self.survey.uuid}/?token={self.survey.test_token}')
        viewer = make_member(self.org, 'test_viewer', role='viewer')
        self.assertIsNone(self.api.get(f'{self.base}/share', token=mint(viewer)[0]).json()['test_url'])

    # ── QR ──

    def test_png_qr_of_the_survey_link(self):
        """
        GIVEN a published survey
        WHEN qr.png and qr.svg are requested
        THEN they are a PNG and an SVG of exactly the survey URL
        """
        from survey.share import qr_image
        png = self.api.get(f'{self.base}/share/qr.png')
        self.assertEqual(png['Content-Type'], 'image/png')
        self.assertEqual(png.content, qr_image(f'{SITE}/surveys/{self.survey.uuid}/', 'png')[0])
        svg = self.api.get(f'{self.base}/share/qr.svg', {'size': 4})
        self.assertEqual(svg['Content-Type'], 'image/svg+xml')
        self.assertIn(b'<svg', svg.content)

    def test_qr_of_a_tracked_link(self):
        """
        GIVEN a tracked link
        WHEN the QR is requested with link=<id>
        THEN it encodes the link's URL
        """
        from survey.share import qr_image
        link = TrackedLink.objects.create(survey=self.survey, utm_source='poster')
        png = self.api.get(f'{self.base}/share/qr.png', {'link': link.pk})
        self.assertEqual(png.content, qr_image(link.build_url(SITE), 'png')[0])

    def test_draft_qr_is_not_shareable(self):
        """
        GIVEN a draft survey
        WHEN a QR is requested
        THEN 409 not_shareable
        """
        self.survey.status = 'draft'
        self.survey.save()
        response = self.api.get(f'{self.base}/share/qr.png')
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()['error'], 'not_shareable')

    # ── tracked links ──

    def test_create_and_count(self):
        """
        GIVEN an editor creates a link utm_source=flyer
        WHEN one response starts with those parameters
        THEN the list shows the link, its https URL and started 1, and the creation is audited
        """
        created = self.api.post(f'{self.base}/tracked-links', {'utm_source': ' flyer ', 'utm_medium': 'print'})
        self.assertEqual(created.status_code, 200, created.content)
        self.assertEqual(created.json()['url'], f'{SITE}/surveys/{self.survey.uuid}/?utm_source=flyer&utm_medium=print')
        session = SurveySession.objects.create(survey=self.survey)
        SurveyEvent.objects.create(session=session, event_type='session_start',
                                   metadata={'utm_source': 'flyer', 'utm_medium': 'print'})
        items = self.api.get(f'{self.base}/tracked-links').json()['items']
        self.assertEqual(len(items), 1)
        self.assertEqual((items[0]['started'], items[0]['completed']), (1, 0))
        self.assertTrue(AuditLog.objects.filter(action='tracked_link_create').exists())

    def test_viewer_cannot_create(self):
        """
        GIVEN a viewer's token with surveys:write
        WHEN it posts a tracked link
        THEN 403 forbidden_role
        """
        viewer = make_member(self.org, 'link_viewer', role='viewer')
        response = self.api.post(f'{self.base}/tracked-links', {'utm_source': 'x'}, token=mint(viewer)[0])
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()['error'], 'forbidden_role')

    def test_limit_and_delete(self):
        """
        GIVEN a survey already holding the maximum number of links
        WHEN another is posted, and then one is deleted
        THEN the post is 409 limit_reached and the delete removes it
        """
        from survey import share
        TrackedLink.objects.bulk_create([TrackedLink(survey=self.survey, utm_source=f's{i}')
                                         for i in range(share.MAX_TRACKED_LINKS)])
        response = self.api.post(f'{self.base}/tracked-links', {'utm_source': 'one-more'})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()['error'], 'limit_reached')
        link = TrackedLink.objects.filter(survey=self.survey).first()
        self.assertEqual(self.api.call('DELETE', f'{self.base}/tracked-links/{link.pk}').status_code, 200)
        self.assertFalse(TrackedLink.objects.filter(pk=link.pk).exists())

    # ── embed hosts ──

    def test_invalid_embed_host(self):
        """
        GIVEN hosts with one invalid entry
        WHEN they are put
        THEN 400 naming it, nothing saved; a valid list is saved on the survey
        """
        response = self.api.call('PUT', f'{self.base}/share/embed-hosts', {'hosts': ['example.org', 'not a host!']})
        self.assertEqual(response.status_code, 400)
        self.assertIn('not a host!', str(response.json()))
        self.survey.refresh_from_db()
        self.assertEqual(self.survey.embed_allowed_hosts, [])
        ok = self.api.call('PUT', f'{self.base}/share/embed-hosts', {'hosts': ['Example.org', '*.city.gov']})
        self.assertEqual(ok.json()['hosts'], ['example.org', '*.city.gov'])


@override_settings(SITE_URL=SITE)
class SharePageLinksTest(TestCase):
    def test_share_page_links_are_https_and_canonical(self):
        """
        GIVEN a tracked link on the canonical survey and a proxy saying https
        WHEN the Share page renders
        THEN the link starts with https:// and is listed
        """
        org, owner = make_pro_org()
        survey, _section = make_v1_survey(org, owner, status='published')
        TrackedLink.objects.create(survey=survey, utm_source='newsletter')
        self.client.force_login(owner)
        html = self.client.get(f'/editor/surveys/{survey.uuid}/share/', HTTP_X_FORWARDED_PROTO='https').content.decode()
        self.assertIn(f'https://testserver/surveys/{survey.uuid}/?utm_source=newsletter', html)
