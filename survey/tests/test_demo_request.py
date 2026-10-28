"""Tests for the `demo-request` capability (openspec/specs/demo-request/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase, Client, override_settings
from django.contrib.auth.models import User
from django.utils import timezone
from unittest import mock
import re
import uuid
from survey.models import Story
from survey.models import SurveyEvent
from django.core import mail
from survey.models import AbuseEvent


@override_settings(CONTACT_EMAIL="leads@mapsurvey.test")
class DemoRequestTest(TestCase):
    """Two-step "Request a demo" at /demo/ (change request-demo-form, issue #288)."""

    LOCMEM = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache",
                          "LOCATION": "demo-request-test"}}

    def setUp(self):
        from django.core.cache import caches
        from survey.tasks import notify_demo_request
        # Run the Celery task in-process: the test suite has no broker.
        self._delay = mock.patch('survey.tasks.notify_demo_request.delay',
                                 side_effect=lambda pk, stage: notify_demo_request(pk, stage))
        self._delay.start()
        self.addCleanup(self._delay.stop)
        caches["default"].clear()

    def _fresh_limits(self):
        # The locmem cache outlives a single test: without this, one test's counters leak into
        # the next and the limit trips early or late depending on the order tests run in.
        from django.core.cache import caches
        caches["default"].clear()

    def _submit_email(self, client=None, email="planner@city.example", src="hero", **extra):
        client = client or Client()
        with self.captureOnCommitCallbacks(execute=True):
            return client.post("/demo/", {"email": email, "src": src, **extra})

    def test_step_one_asks_only_for_an_email(self):
        """
        GIVEN an anonymous visitor
        WHEN /demo/ is requested
        THEN it renders "What's your work email?", one visible email input, a "Next" button, a trust-page
             link and a noindex tag, and no consent box or CAPTCHA
        """
        resp = Client().get("/demo/?src=hero")
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        form = html[html.index('class="demo-form"'):html.index("</form>")]
        self.assertIn('type="email" name="email"', form)
        self.assertNotIn('type="checkbox"', form)
        self.assertNotIn("cf-turnstile", form)
        self.assertNotIn('<textarea', form)
        self.assertIn('name="src" value="hero"', form)
        self.assertIn(">Next</button>", form)
        self.assertContains(resp, "What's your work email?")
        self.assertIn('href="/trust/#data-privacy"', form)
        self.assertContains(resp, '<meta name="robots" content="noindex, follow">')

    def test_email_creates_the_lead_and_redirects_to_step_two(self):
        """
        GIVEN a visitor on step one
        WHEN they submit a valid email
        THEN one DemoRequest is stored with that email and source, and they are sent to its step-two URL
        """
        from survey.models import DemoRequest

        resp = self._submit_email()
        self.assertEqual(DemoRequest.objects.count(), 1)
        row = DemoRequest.objects.get()
        self.assertEqual(row.email, "planner@city.example")
        self.assertEqual(row.source, "hero")
        self.assertIsNone(row.details_at)
        self.assertRedirects(resp, "/demo/%s/" % row.key)

    def test_unknown_source_is_stored_as_direct(self):
        """
        GIVEN a source outside the allow-list, or none at all
        WHEN the email is submitted
        THEN the row's source is 'direct'
        """
        from survey.models import DemoRequest

        self._submit_email(email="a@x.example", src="<script>")
        self._submit_email(email="b@x.example", src="")
        self.assertEqual(sorted(DemoRequest.objects.values_list("source", flat=True)), ["direct", "direct"])

    def test_invalid_email_redisplays_with_an_error(self):
        """
        GIVEN a visitor who mistypes their address
        WHEN step one is submitted
        THEN the form comes back with an error and nothing is stored
        """
        from survey.models import DemoRequest

        resp = self._submit_email(email="not-an-email")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'aria-invalid="true"')
        self.assertEqual(DemoRequest.objects.count(), 0)

    def test_step_one_mails_contact_email(self):
        """
        GIVEN the lead must reach us even if the visitor stops here
        WHEN step one is submitted
        THEN one email "Demo request: <email>" goes to CONTACT_EMAIL with the admin link
        """
        from django.core import mail

        self._submit_email()
        self.assertEqual(len(mail.outbox), 1)
        msg = mail.outbox[0]
        self.assertEqual(msg.to, ["leads@mapsurvey.test"])
        self.assertEqual(msg.subject, "Demo request: planner@city.example")
        self.assertIn("/admin/survey/demorequest/", msg.body)
        self.assertIn("Source: hero", msg.body)

    def test_mail_failure_does_not_lose_the_lead(self):
        """
        GIVEN the broker is down and the inline send fails too
        WHEN step one is submitted
        THEN the row is still stored and the visitor still reaches step two
        """
        from survey.models import DemoRequest

        self._delay.stop()
        with mock.patch('survey.tasks.notify_demo_request.delay', side_effect=OSError('broker down')), \
                mock.patch('survey.demo_request.send_notification', side_effect=RuntimeError('smtp down')):
            resp = self._submit_email()
        self._delay.start()
        self.assertEqual(DemoRequest.objects.count(), 1)
        self.assertEqual(resp.status_code, 302)

    def test_step_two_completes_the_same_row(self):
        """
        GIVEN a lead created by step one
        WHEN the visitor submits name, organisation, project and timeline
        THEN the same row is updated, details_at is set, a details email is sent and the done state shows
        """
        from django.core import mail
        from survey.models import DemoRequest

        self._submit_email()
        row = DemoRequest.objects.get()
        page = Client().get("/demo/%s/" % row.key)
        self.assertContains(page, "Request received for planner@city.example")
        self.assertContains(page, "Skip for now")
        self.assertContains(page, "Tell us a bit more")
        with self.captureOnCommitCallbacks(execute=True):
            resp = Client().post("/demo/%s/" % row.key, {
                "name": "Ana", "organisation": "City of Olney",
                "project": "Unsafe crossings near schools", "timeline": "this_quarter",
            })
        self.assertContains(resp, "Thanks — we'll be in touch")
        row.refresh_from_db()
        self.assertEqual((row.name, row.organisation, row.timeline), ("Ana", "City of Olney", "this_quarter"))
        self.assertIsNotNone(row.details_at)
        self.assertEqual(DemoRequest.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(mail.outbox[1].subject, "Demo request details: planner@city.example — City of Olney")
        self.assertIn("Unsafe crossings near schools", mail.outbox[1].body)

    def test_step_two_can_be_skipped(self):
        """
        GIVEN a lead created by step one
        WHEN the visitor follows "Skip for now"
        THEN the done state shows and the row keeps only the email
        """
        from survey.models import DemoRequest

        self._submit_email()
        row = DemoRequest.objects.get()
        resp = Client().get("/demo/%s/?skip=1" % row.key)
        self.assertContains(resp, "Thanks — we'll be in touch")
        row.refresh_from_db()
        self.assertIsNone(row.details_at)
        self.assertEqual(row.name, "")

    def test_completed_or_expired_key_shows_done_and_accepts_no_edits(self):
        """
        GIVEN a row whose details are already in, and a row older than seven days
        WHEN their step-two URLs are requested or posted to
        THEN both show the done state and nothing changes
        """
        from datetime import timedelta
        from django.utils import timezone
        from survey.models import DemoRequest

        done = DemoRequest.objects.create(email="d@x.example", details_at=timezone.now(), name="Kept")
        old = DemoRequest.objects.create(email="o@x.example",
                                         created_at=timezone.now() - timedelta(days=8))
        for row in (done, old):
            self.assertContains(Client().get("/demo/%s/" % row.key), "Thanks — we'll be in touch")
            Client().post("/demo/%s/" % row.key, {"name": "Changed"})
        done.refresh_from_db(); old.refresh_from_db()
        self.assertEqual(done.name, "Kept")
        self.assertEqual(old.name, "")

    def test_unknown_key_is_404(self):
        """
        GIVEN a step-two key that matches no row
        WHEN it is requested
        THEN the response is 404
        """
        import uuid
        self.assertEqual(Client().get("/demo/%s/" % uuid.uuid4()).status_code, 404)

    def test_signed_in_creator_is_prefilled_and_attributed(self):
        """
        GIVEN a signed-in creator
        WHEN they open /demo/ and submit
        THEN the email is pre-filled and the row references their account
        """
        from survey.models import DemoRequest

        user = User.objects.create_user("demo-user", email="creator@org.example", password="pw")
        c = Client()
        c.force_login(user)
        self.assertContains(c.get("/demo/"), 'value="creator@org.example"')
        self._submit_email(client=c, email="creator@org.example")
        self.assertEqual(DemoRequest.objects.get().user, user)

    def test_each_step_emits_one_event(self):
        """
        GIVEN the leads must be countable by step and surface
        WHEN step one and then step two are submitted
        THEN two demo_requested events are emitted, stage email then details, with the source
        """
        from survey.models import DemoRequest

        with mock.patch('posthog.disabled', False), mock.patch('posthog.capture') as capture:
            self._submit_email(src="services")
            row = DemoRequest.objects.get()
            with self.captureOnCommitCallbacks(execute=True):
                Client().post("/demo/%s/" % row.key, {"timeline": "asap"})
        self.assertEqual(capture.call_count, 2)
        first, second = capture.call_args_list
        self.assertEqual(first.args[0], "demo_requested")
        self.assertEqual(first.kwargs["properties"]["stage"], "email")
        self.assertEqual(first.kwargs["properties"]["source"], "services")
        self.assertEqual(second.kwargs["properties"]["stage"], "details")
        self.assertEqual(second.kwargs["properties"]["timeline"], "asap")
        # No cookie and no session: the id is derived from the row, so the event is never dropped.
        self.assertEqual(first.kwargs["distinct_id"], "demo_request_%s" % row.pk)

    def test_analytics_failure_does_not_lose_the_lead(self):
        """
        GIVEN emitting the event raises
        WHEN step one is submitted
        THEN the row is stored and the visitor still reaches step two
        """
        from survey.models import DemoRequest

        with mock.patch('posthog.disabled', False), \
                mock.patch('posthog.capture', side_effect=RuntimeError('down')):
            resp = self._submit_email()
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(DemoRequest.objects.count(), 1)

    def test_no_respondent_analytics_row(self):
        """
        GIVEN SurveyEvent measures our customers' respondents, not us
        WHEN a demo request is stored
        THEN no SurveyEvent is written
        """
        from survey.models import SurveyEvent

        before = SurveyEvent.objects.count()
        self._submit_email()
        self.assertEqual(SurveyEvent.objects.count(), before)

    def test_filled_honeypot_stores_nothing_and_looks_like_success(self):
        """
        GIVEN a bot that fills every field
        WHEN it posts step one with the honeypot filled
        THEN nothing is stored or mailed, an AbuseEvent is logged, and it is redirected to a done page
        """
        from django.core import mail
        from survey.abuse import HONEYPOT_FIELD_NAME
        from survey.models import AbuseEvent, DemoRequest

        resp = self._submit_email(**{HONEYPOT_FIELD_NAME: "http://spam.example"})
        self.assertRedirects(resp, "/demo/done/")
        self.assertContains(Client().get("/demo/done/"), "Thanks — we'll be in touch")
        self.assertEqual(DemoRequest.objects.count(), 0)
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(AbuseEvent.objects.filter(defense="honeypot", detail="demo_request").count(), 1)

    def test_per_ip_limit_returns_429(self):
        """
        GIVEN a per-IP hourly limit of 2 already spent by valid submissions
        WHEN the same IP submits step one again
        THEN it gets 429 with Retry-After, no row is created, and a ratelimit AbuseEvent is logged
        """
        from survey.models import AbuseEvent, DemoRequest

        with override_settings(DEMO_REQUEST_LIMIT_HOUR=2, DEMO_REQUEST_LIMIT_DAY=10, CACHES=self.LOCMEM):
            self._fresh_limits()
            self._submit_email(email="1@x.example")
            self._submit_email(email="2@x.example")
            resp = self._submit_email(email="3@x.example")
        self.assertEqual(resp.status_code, 429)
        self.assertIn("Retry-After", resp)
        self.assertEqual(DemoRequest.objects.count(), 2)
        self.assertEqual(AbuseEvent.objects.filter(defense="ratelimit", detail="demo_hour").count(), 1)

    def test_invalid_submissions_do_not_spend_the_budget(self):
        """
        GIVEN a per-IP hourly limit of 1
        WHEN a visitor mistypes their email twice, then submits a valid one
        THEN the valid one is accepted
        """
        from survey.models import DemoRequest

        with override_settings(DEMO_REQUEST_LIMIT_HOUR=1, DEMO_REQUEST_LIMIT_DAY=10, CACHES=self.LOCMEM):
            self._fresh_limits()
            self._submit_email(email="bad")
            self._submit_email(email="worse@")
            resp = self._submit_email(email="good@x.example")
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(DemoRequest.objects.count(), 1)

    def _demo_pages(self):
        from survey.models import DemoRequest
        row = DemoRequest.objects.create(email="p@x.example")
        return {"email": "/demo/", "details": "/demo/%s/" % row.key, "done": "/demo/done/"}

    def test_every_state_is_a_focused_page(self):
        """
        GIVEN the three states of the demo page
        WHEN each is rendered
        THEN none carries the landing navbar or the landing footer, and each has the wordmark linking home
        """
        for state, url in self._demo_pages().items():
            html = Client().get(url).content.decode()
            self.assertNotIn('class="landing-nav"', html, state)
            self.assertNotIn('class="landing-footer"', html, state)
            self.assertIn('<a href="/" class="demo-top__brand">', html, state)

    def test_carousel_shows_quotes_from_published_stories(self):
        """
        GIVEN the Pszów and Whitehouse stories are published
        WHEN any state of the demo page is rendered
        THEN the carousel carries the three quotes with names, organisations, initials and story links,
             only the first is visible without JavaScript, and the dots start hidden
        """
        from survey.models import Story

        Story.objects.create(title="Pszów", slug="pszow-microplanning", is_published=True)
        Story.objects.create(title="Whitehouse", slug="whitehouse-dog-bins", is_published=True)
        for state, url in self._demo_pages().items():
            html = Client().get(url).content.decode()
            carousel = html[html.index('aria-roledescription="carousel"'):html.index("</aside>")]
            self.assertEqual(carousel.count('class="demo-quote"'), 3, state)
            figures = re.findall(r'<figure class="demo-quote"[^>]*>', carousel)
            self.assertEqual([("hidden" in f) for f in figures], [False, True, True], state)
            for text in ("giving a voice to the people who use the bus station",
                         "I am very impressed with the tool",
                         "probably unheard of in local government"):
                self.assertIn(text, carousel, state)
            for who in ("Anna M. Pyziak", "Towarzystwo Urbanistów Polskich", "Julian Thomas",
                        "Cliff Schraibman", "Whitehouse Community Council"):
                self.assertIn(who, carousel, state)
            self.assertIn(">AP<", carousel, state)
            self.assertIn(">JT<", carousel, state)
            self.assertIn('href="/stories/pszow-microplanning/" class="demo-quote__link"', carousel, state)
            self.assertIn('href="/stories/whitehouse-dog-bins/" class="demo-quote__link"', carousel, state)
            self.assertIn('class="demo-quotes__dots" role="tablist"', carousel, state)
            self.assertNotIn("4,500", carousel, state)

    def test_quote_of_an_unpublished_story_is_not_shown(self):
        """
        GIVEN only the Whitehouse story is published
        WHEN /demo/ is rendered
        THEN the Pszów quote is absent and both Whitehouse quotes are shown
        """
        from survey.models import Story

        Story.objects.create(title="Pszów", slug="pszow-microplanning", is_published=False)
        Story.objects.create(title="Whitehouse", slug="whitehouse-dog-bins", is_published=True)
        resp = Client().get("/demo/")
        self.assertNotContains(resp, "Anna M. Pyziak")
        self.assertContains(resp, "Julian Thomas")
        self.assertContains(resp, "Cliff Schraibman")

    def test_no_published_story_no_carousel(self):
        """
        GIVEN none of the quoted stories is published
        WHEN /demo/ is rendered
        THEN the carousel is not rendered at all
        """
        self.assertNotContains(Client().get("/demo/"), 'aria-roledescription="carousel"')

    def test_initials_skip_the_middle_initial(self):
        """
        GIVEN a name with a middle initial
        WHEN its avatar initials are built
        THEN they are the first and last name's letters
        """
        from survey.demo_request import _initials

        self.assertEqual(_initials("Anna M. Pyziak"), "AP")
        self.assertEqual(_initials("Cliff Schraibman"), "CS")
        self.assertEqual(_initials("Plato"), "P")

    def test_logo_strip_from_published_stories_with_a_logo(self):
        """
        GIVEN a published story with a credit logo, one without a logo, and an unpublished one with a logo
        WHEN /demo/ is rendered
        THEN only the first appears in the logo strip, with its credit as alt text and a link to the story
        """
        from survey.models import Story

        Story.objects.create(title="Olney", slug="olney", is_published=True,
                             credit="City of Olney", credit_logo="stories/olney-logo.png")
        Story.objects.create(title="No logo", slug="no-logo", is_published=True, credit="Nobody")
        Story.objects.create(title="Draft", slug="draft", is_published=False,
                             credit="Draft Org", credit_logo="stories/draft-logo.png")
        html = Client().get("/demo/").content.decode()
        strip = html[html.index('class="demo-logos"'):]
        self.assertIn('href="/stories/olney/"', strip)
        self.assertIn('alt="City of Olney"', strip)
        self.assertNotIn("no-logo", strip)
        self.assertNotIn("draft", strip)

    def test_no_logos_no_strip(self):
        """
        GIVEN no published story has a credit logo
        WHEN /demo/ is rendered
        THEN the logo strip is not rendered
        """
        self.assertNotContains(Client().get("/demo/"), 'class="demo-logos"')

    def test_admin_lists_requests_read_only(self):
        """
        GIVEN a stored request
        WHEN a superuser opens the DemoRequest changelist
        THEN the row is listed and there is no add button
        """
        from survey.models import DemoRequest

        DemoRequest.objects.create(email="lead@x.example", organisation="Olney", source="footer")
        admin_user = User.objects.create_superuser("demo-admin", "a@x.example", "pw")
        c = Client()
        c.force_login(admin_user)
        resp = c.get("/admin/survey/demorequest/")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "lead@x.example")
        self.assertNotContains(resp, "/admin/survey/demorequest/add/")
        self.assertEqual(c.get("/admin/survey/demorequest/add/").status_code, 403)
