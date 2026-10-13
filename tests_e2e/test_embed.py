"""End-to-end: a survey embedded on another site is completed inside the frame
(change embed-surveys, #284).

The host page is served by a throwaway HTTP server on 127.0.0.1, so the frame
is genuinely cross-site (127.0.0.1 and localhost are different sites for
cookies and Fetch Metadata); the survey inside it is the real dev server. A
real loopback server rather than `page.route`: Chromium's Local Network Access
checks block a frame to a loopback address from any origin it cannot classify
as local, which includes a route-fulfilled page. The allow-list is left empty
because its entries are https-only (the allow-list itself is covered by unit
tests). That is the one check the unit tests cannot make: that
the session and CSRF cookies are actually sent from inside a third-party
frame. It needs the dev server started with `CROSS_SITE_COOKIES=1` (Secure
cookies on http://localhost are accepted by Chromium and Firefox); without
it the test skips rather than fails. WebKit refuses a Secure cookie from plain
http://localhost altogether, so under `--browser webkit` this test skips too:
Safari is verified against an HTTPS preview, not locally.
"""
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from survey.models import Answer, Question, SurveySection, SurveySession



@pytest.fixture
def embeddable_survey(test_user):
    from tests_e2e.conftest import _build_survey, _purge_survey

    survey = _build_survey(
        name=f"e2e-embed-{uuid.uuid4().hex[:6]}",
        basemaps=["streets"],
        owner=test_user,
        sections_count=2,
        add_point=False,
    )
    sections = list(SurveySection.objects.filter(survey_header=survey).order_by("id"))
    for i, section in enumerate(sections):
        section.layout = "form"
        section.save(update_fields=["layout"])
        Question.objects.create(
            survey_section=section, name=f"Question {i + 1}", input_type="text_line",
            order_number=1, code=f"Q{i + 1}", required=True,
        )
    survey.redirect_url = "https://example.com/after"
    survey.save(update_fields=["redirect_url"])
    yield survey
    _purge_survey(survey)


@pytest.fixture
def host_page(base_url, embeddable_survey):
    """Serve the embedding page from its own loopback origin; yield its URL."""
    body = _host_page_html(base_url, embeddable_survey).encode()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}/park-consultation/"
    server.shutdown()


def _host_page_html(base_url, survey):
    return f"""<!doctype html><html><body>
    <h1>Park consultation</h1>
    <iframe id="ms" src="{base_url}/surveys/{survey.uuid}/?embed=1" title="{survey.name}"
            style="width:100%;height:400px;border:0;" allow="geolocation; fullscreen"></iframe>
    <script async src="{base_url}/embed.js"></script>
    </body></html>"""


def test_survey_completes_inside_a_cross_site_frame(browser, base_url, embeddable_survey, host_page):
    """
    GIVEN a page on another origin that frames a published two-section survey
    WHEN a respondent answers both sections inside the frame
    THEN one session holds both answers, the frame shows the thanks page with the
         top-window Continue link, and the frame grew to fit the form
    """
    context = browser.new_context()
    page = context.new_page()

    page.goto(host_page)
    frame = page.frame_locator("#ms")
    frame.locator('input[name="Q1"]').wait_for(timeout=15000)

    # Playwright strips Set-Cookie from response.headers; the context jar says
    # what the dev server handed out.
    session_cookie = next((c for c in context.cookies() if c["name"] == "sessionid"), None)
    if session_cookie is None or session_cookie.get("sameSite") != "None":
        pytest.skip("dev server runs without CROSS_SITE_COOKIES=1; cookies cannot cross into the frame")

    frame.locator('input[name="Q1"]').fill("Blue")
    frame.locator("input.next_button[type=submit]").first.click()
    frame.locator('input[name="Q2"]').wait_for(timeout=15000)
    frame.locator('input[name="Q2"]').fill("Berlin")
    frame.locator("input.next_button[type=submit]").first.click()

    continue_link = frame.locator('a[target="_top"][href="https://example.com/after"]')
    continue_link.wait_for(timeout=15000)
    assert page.url == host_page, "the host page itself must not navigate"

    sessions = SurveySession.objects.filter(survey=embeddable_survey)
    assert sessions.count() == 1
    answers = {a.question.code: a for a in Answer.objects.filter(survey_session=sessions.first())}
    assert set(answers) == {"Q1", "Q2"}

    height = int(page.evaluate("parseInt(document.getElementById('ms').style.height, 10)"))
    assert height != 400, "embed.js should have resized the frame to the form's height"
    assert 300 <= height <= 1500, f"frame height {height}px: the height loop is back (document, not card, measured)"
    context.close()
