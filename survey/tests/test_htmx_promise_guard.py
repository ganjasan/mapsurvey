"""Tests for the `htmx-promise-guard` capability (openspec/specs/htmx-promise-guard/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import SimpleTestCase
import re


class HtmxPromiseGuardTest(SimpleTestCase):
    """htmx 1.9's htmx.ajax() rejects its promise with a bare reject() (value:
    undefined) on network error, abort, timeout or a missing target. Every
    unhandled one lands in PostHog error tracking as "Non-Error promise
    rejection captured with value: undefined" with no stack (backlog #194).
    js/htmx_promise_guard.js wraps htmx.ajax once so the returned promise is
    always handled; these canaries pin that contract."""

    GUARD = 'js/htmx_promise_guard.js'

    @staticmethod
    def _app_root():
        import pathlib

        return pathlib.Path(__file__).resolve().parent.parent

    def test_guard_wraps_htmx_ajax_and_attaches_a_catch(self):
        """
        GIVEN the htmx promise guard static file
        WHEN its source is inspected
        THEN it replaces window.htmx.ajax and attaches a rejection handler to
             the returned promise, because without both the wrap is a no-op
        """
        source = (self._app_root() / 'assets' / self.GUARD).read_text()
        self.assertIn('window.htmx.ajax = function', source)
        self.assertIn('p.catch(function () {})', source)
        self.assertIn('return p;', source)

    def test_every_template_loading_htmx_also_loads_the_guard(self):
        """
        GIVEN every template shipped with the survey app
        WHEN one includes the htmx library
        THEN it includes js/htmx_promise_guard.js after it, because a base
             template that loads htmx without the guard reintroduces the
             unhandled rejections on every page built on it
        """
        root = self._app_root() / 'templates'
        offenders = []
        for path in sorted(root.rglob('*.html')):
            source = path.read_text()
            if 'htmx.org' not in source:
                continue
            htmx_at = source.index('htmx.org')
            guard_at = source.find(self.GUARD)
            if guard_at < htmx_at:
                offenders.append(str(path.relative_to(root)))

        self.assertEqual(
            offenders, [],
            'Templates loading htmx without js/htmx_promise_guard.js after it: '
            + ', '.join(offenders),
        )

    #: Depth-0 characters that would hide a top-level comma from a naive scan.
    _OPEN, _CLOSE = '({[', ')}]'

    @classmethod
    def _call_end(cls, source, open_paren):
        """Index just past the ) that closes the ( at open_paren."""
        depth = 0
        for i in range(open_paren, len(source)):
            char = source[i]
            if char in cls._OPEN:
                depth += 1
            elif char in cls._CLOSE:
                depth -= 1
                if depth == 0:
                    return i + 1
        return len(source)

    @classmethod
    def _has_rejection_handler(cls, source, then_open):
        """True when the .then( at then_open has a second argument at depth 0,
        or a .catch( chained right after it."""
        depth = 0
        for i in range(then_open, len(source)):
            char = source[i]
            if char in cls._OPEN:
                depth += 1
            elif char in cls._CLOSE:
                depth -= 1
                if depth == 0:
                    return source[i + 1:i + 20].lstrip().startswith('.catch(')
            elif char == ',' and depth == 1:
                return True
        return False

    def test_chained_then_on_htmx_ajax_carries_a_rejection_handler(self):
        """
        GIVEN every template and static JS file in the survey app
        WHEN a .then( is chained on an htmx.ajax(...) call
        THEN the statement carries a rejection handler (second .then argument
             or a .catch), because the guard marks only the base promise
             handled — a derived promise still rejects unhandled
        """
        import re

        root = self._app_root()
        offenders = []
        paths = sorted((root / 'templates').rglob('*.html'))
        paths += sorted((root / 'assets' / 'js').rglob('*.js'))
        for path in paths:
            source = path.read_text()
            for match in re.finditer(r'htmx\.ajax\s*\(', source):
                call_end = self._call_end(source, match.end() - 1)
                tail = source[call_end:call_end + 20].lstrip()
                if not tail.startswith('.then('):
                    continue
                then_open = source.index('.then(', call_end) + len('.then')
                if not self._has_rejection_handler(source, then_open):
                    line = source.count('\n', 0, match.start()) + 1
                    offenders.append(f'{path.relative_to(root)}:{line}')

        self.assertEqual(
            offenders, [],
            'htmx.ajax(...).then(...) without a rejection handler — the derived '
            'promise rejects unhandled (value: undefined): ' + ', '.join(offenders),
        )
