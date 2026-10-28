"""Tests for the `client-error-visibility` capability (openspec/specs/client-error-visibility/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import SimpleTestCase
import re


class ExternalScriptCrossOriginTest(SimpleTestCase):
    """Third-party scripts must be loaded so that their exceptions stay readable.

    A script from another origin that throws reaches `window.onerror` — and
    therefore PostHog — as `Script error.` with no message, file, line or stack,
    unless its tag carries `crossorigin` and the host answers with CORS headers.
    That is not hypothetical: the first recorded editor session produced two such
    blanked errors on the analytics page, and we still do not know what threw.

    All twelve CDN hosts we load from answer `Access-Control-Allow-Origin: *`, so
    the attribute is safe. Adding it to a host that does NOT would make the
    browser refuse the script outright, so a new host needs that check first.
    """

    #: Matches a whole <script> element, including tags split across lines.
    SCRIPT_TAG = re.compile(r'<script\b[^>]*>', re.IGNORECASE | re.DOTALL)

    def test_every_external_script_tag_carries_crossorigin(self):
        """
        GIVEN every template shipped with the survey app
        WHEN each script tag loading from an external origin is inspected
        THEN it carries a crossorigin attribute, so its errors arrive with detail
        """
        import pathlib

        root = pathlib.Path(__file__).resolve().parent.parent / 'templates'
        offenders = []
        for path in root.rglob('*.html'):
            for tag in self.SCRIPT_TAG.findall(path.read_text()):
                if 'src="https://' not in tag and "src='https://" not in tag:
                    continue
                if 'crossorigin' in tag:
                    continue
                src = re.search(r'src=["\'](https://[^"\']+)', tag)
                offenders.append(
                    f'{path.relative_to(root)}: {src.group(1) if src else tag[:60]}'
                )

        self.assertEqual(
            offenders, [],
            'External <script> tags without crossorigin="anonymous" report their '
            'exceptions as a bare "Script error." with no message, file or stack. '
            'Add the attribute — and if the host is new, first confirm it answers '
            'Access-Control-Allow-Origin, or the browser will refuse the script '
            'entirely: ' + '; '.join(offenders),
        )

    def test_the_guard_would_catch_a_missing_attribute(self):
        """
        GIVEN a guard that passes vacuously is worse than no guard
        WHEN the same matching is applied to a tag without the attribute
        THEN it is recognised as an offender

        Cheap insurance against the regex quietly ceasing to match anything —
        which would look identical to "all templates are fine".
        """
        bad = '<script src="https://cdn.example.com/x.js"></script>'
        good = '<script src="https://cdn.example.com/x.js" crossorigin="anonymous"></script>'
        multiline = (
            '<script src="https://cdn.example.com/x.js"\n'
            '   integrity="sha512-abc"\n'
            '   crossorigin="anonymous"></script>'
        )

        found = self.SCRIPT_TAG.findall(bad)
        self.assertEqual(len(found), 1)
        self.assertNotIn('crossorigin', found[0])

        self.assertIn('crossorigin', self.SCRIPT_TAG.findall(good)[0])
        self.assertIn('crossorigin', self.SCRIPT_TAG.findall(multiline)[0])
