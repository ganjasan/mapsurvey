"""Tests for the `ui-internationalization` capability (openspec/specs/ui-internationalization/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase, SimpleTestCase, Client
from django.contrib.auth.models import User
from django.contrib.gis.geos import Point
from django.utils import translation
from django.template import Template, Context
from io import BytesIO
from unittest import mock
from unittest.mock import patch
import contextlib
import json
import re
import zipfile
from survey.models import SurveyHeader, SurveySection, Membership
from survey.serialization import import_survey_from_zip
from django.conf import settings
import os
import tempfile
from survey.tests.helpers import _make_org


class TranslationCatalogHygieneTest(SimpleTestCase):
    """Catch the corruption class that made `ru` render the wrong strings.

    The `ru` catalog shipped `Email address` as «Поиск адреса...» and `Archived`
    as «Архитектура» -- msgstr values belonging to *other* msgids, the signature
    of a catalog whose entries slipped out of alignment.

    Scope, deliberately narrow: this detects one msgstr reused across msgids
    that are not synonyms. It cannot detect a translation that is unique but
    simply wrong -- `Your responses have been recorded.` rendered as «Ваша
    учетная запись активирована.» ("your account has been activated") passes
    every mechanical check there is. Semantic correctness needs a reader.
    """

    #: Catalogs we maintain (openspec: creator-ui-localization). Wider than
    #: settings.LANGUAGES on purpose: a catalog is filled here first and only
    #: joins the offered list when complete.
    TARGET_LOCALES = ('en', 'ru', 'id', 'de', 'es', 'fr', 'pt', 'pl')

    #: Source strings that may legitimately share one translation. Keep this
    #: list short and justified -- every entry is a hole in the check.
    ALLOWED_COLLISIONS = {
        # Marketing headings that are genuinely synonymous in most languages.
        frozenset({'Features', 'Capabilities'}),
        # The same CTA written twice in the source, differing only by "the".
        # The real fix is one string in the templates; until then a shared
        # translation is correct rather than a symptom.
        frozenset({'Try Demo Survey', 'Try the Demo Survey'}),
        # The Build sidebar entry and the Translations tab's row label for the
        # same page (change translation-table); most languages have one name
        # for it.
        frozenset({'Thanks page', 'Thank-you page'}),
        # A marketing table heading and the Responses export button: the same
        # noun phrase in either order, one translation in most languages.
        frozenset({'Data export', 'Export data'}),
        # A landing heading and the hero banner's secondary link (change
        # changelog-hero): the same question, with or without "this".
        frozenset({'How it works', 'How this works'}),
    }

    @staticmethod
    def _same_but_for_case(msgids):
        """Source strings that differ only in capitalisation.

        "Check Your Email" and "Check your email" both exist in the templates --
        one as a heading, one as body text. They mean the same thing and SHOULD
        share a translation, so flagging them teaches the reader to ignore this
        test. Enumerating each pair in ALLOWED_COLLISIONS would do the same
        damage more slowly. The real fix is one string in the source; this rule
        stops the duplication from masking the corruption the test is for.
        """
        return len({m.casefold() for m in msgids}) == 1

    @staticmethod
    def _same_but_for_plural(msgids):
        """Source strings that are one word set, singular vs plural.

        Indonesian marks no plural: `Section` and `Sections` are both
        «Bagian», and so are Question/Questions, Answer/Answers,
        Session/Sessions, User/Users -- thirteen pairs in one catalog. That is
        the language, not a shifted catalog, and the same will happen for any
        other language without plural inflection. The rule is deliberately
        narrow: identical once case, spaces and a trailing `s` are removed, so
        `Base maps`/`Basemap` passes while `Delete`/`Remove` (a real bug this
        test caught in the Indonesian draft) still fails.
        """
        def stem(msgid):
            word = msgid.casefold().replace(' ', '')
            return word[:-1] if word.endswith('s') else word

        return len({stem(m) for m in msgids}) == 1

    @staticmethod
    def _pairs(text):
        found = re.findall(r'^msgid "(.*)"\n(?:"[^"]*"\n)*msgstr "(.*)"', text, re.M)
        return [(msgid, msgstr) for msgid, msgstr in found if msgid and msgstr]

    def test_no_translation_is_reused_across_different_sources(self):
        """
        GIVEN the catalogs for every language we ship a creator interface in
        WHEN each catalog's filled entries are grouped by their translation
        THEN no translation serves two source strings that are not synonyms,
             because that is how `Testing` came to read as «Рейтинг»
        """
        import collections
        import pathlib

        locales = pathlib.Path(__file__).resolve().parent.parent / 'locale'
        offenders = []
        for code in self.TARGET_LOCALES:
            catalog = locales / code / 'LC_MESSAGES' / 'django.po'
            if not catalog.exists():
                continue
            by_translation = collections.defaultdict(list)
            for msgid, msgstr in self._pairs(catalog.read_text(encoding='utf-8')):
                by_translation[msgstr].append(msgid)
            for msgstr, msgids in by_translation.items():
                if (len(msgids) < 2
                        or frozenset(msgids) in self.ALLOWED_COLLISIONS
                        or self._same_but_for_case(msgids)
                        or self._same_but_for_plural(msgids)):
                    continue
                offenders.append(f'{code}: {msgstr!r} translates {sorted(msgids)}')

        self.assertEqual(
            offenders, [],
            'One translation is serving several source strings, which is how a '
            'shifted catalog looks. Fix the entries or, if they are genuinely '
            'synonymous, add them to ALLOWED_COLLISIONS:\n  '
            + '\n  '.join(offenders),
        )

    def test_every_shipped_language_has_a_catalog(self):
        """
        GIVEN a language offered in the creator interface
        WHEN the locale directory is checked
        THEN a catalog exists for it, so the language cannot be advertised
             while silently falling back to English
        """
        import pathlib

        locales = pathlib.Path(__file__).resolve().parent.parent / 'locale'
        missing = [
            code for code in self.TARGET_LOCALES
            if not (locales / code / 'LC_MESSAGES' / 'django.po').exists()
        ]
        self.assertEqual(missing, [], f'No catalog for: {missing}')

    def test_offered_languages_have_their_plural_forms_filled(self):
        """
        GIVEN a language offered in settings.LANGUAGES
        WHEN its plural entries are inspected
        THEN every form is filled, because a plural keeps its values in
             msgstr_plural and an empty one falls back to English mid-sentence
             — writing to msgstr on such an entry is silently ignored, so this
             string survived several rounds of "fixing" it
        """
        import pathlib

        from django.conf import settings as dj_conf

        # Parsed with a regex rather than polib: polib is available only as a
        # transitive dependency, and a test must not rest on that.
        block = re.compile(
            r'^msgid "(?P<id>[^"]*)"\n'
            r'msgid_plural "[^"]*"\n'
            r'(?P<forms>(?:msgstr\[\d+\] "[^"]*"\n)+)', re.M)

        locales = pathlib.Path(__file__).resolve().parent.parent / 'locale'
        offenders = []
        for code, _name in dj_conf.LANGUAGES:
            if code == dj_conf.LANGUAGE_CODE:
                continue
            catalog = locales / code / 'LC_MESSAGES' / 'django.po'
            if not catalog.exists():
                continue
            for match in block.finditer(catalog.read_text(encoding='utf-8')):
                blank = [i for i, value in enumerate(
                    re.findall(r'msgstr\[\d+\] "([^"]*)"', match.group('forms')))
                    if not value]
                if blank:
                    offenders.append(
                        f"{code}: {match.group('id')[:45]!r} forms {blank} empty")

        self.assertEqual(offenders, [], 'Unfilled plural form:\n  '
                         + '\n  '.join(offenders))

    #: Template directories whose strings a creator reads. Marketing pages
    #: (`survey/templates/*.html` at the top level) are deliberately absent:
    #: their translation is a separate, later piece of work.
    CREATOR_TEMPLATE_DIRS = (
        '/editor/', '/partials/', '/org/',
        '/registration/', '/django_registration/',
    )

    def test_creator_facing_strings_are_translated_in_offered_languages(self):
        """
        GIVEN a language offered in settings.LANGUAGES
        WHEN every msgid that appears in a creator-facing template is checked
        THEN each one is filled, because "the catalog is as complete as the
             German one" is not the same claim: `Sign In`, `Close`, `Logout`,
             `Dashboard`, `Email` and `Languages` occur on BOTH a marketing
             page and an editor screen, so counting against another catalog
             let six English words sit inside a finished German editor
        """
        import pathlib

        from django.conf import settings as dj_conf

        entry = re.compile(
            r'((?:^#: [^\n]*\n)+)'          # occurrence comments
            r'(?:^#[,.] [^\n]*\n)*'         # flags / extracted comments
            r'^msgid "(?P<id>(?:[^"\\]|\\.)*)"\n'
            r'(?P<body>(?:"(?:[^"\\]|\\.)*"\n)*)'
            r'^msgstr "(?P<str>(?:[^"\\]|\\.)*)"\n'
            r'(?P<cont>(?:"(?:[^"\\]|\\.)*"\n)*)', re.M)

        locales = pathlib.Path(__file__).resolve().parent.parent / 'locale'
        offenders = []
        for code, _name in dj_conf.LANGUAGES:
            if code == dj_conf.LANGUAGE_CODE:
                continue
            catalog = locales / code / 'LC_MESSAGES' / 'django.po'
            if not catalog.exists():
                continue
            for match in entry.finditer(catalog.read_text(encoding='utf-8')):
                if not any(d in match.group(1)
                           for d in self.CREATOR_TEMPLATE_DIRS):
                    continue
                if match.group('str') or match.group('cont').strip('"\n '):
                    continue
                if not match.group('id') and not match.group('body'):
                    continue        # the header entry
                offenders.append(f"{code}: {match.group('id')[:60]!r}")

        self.assertEqual(
            offenders, [],
            'A creator-facing string is English in a language we offer:\n  '
            + '\n  '.join(offenders))

    def test_offered_languages_carry_no_fuzzy_translations(self):
        """
        GIVEN a language offered in settings.LANGUAGES
        WHEN its entries are checked for the `fuzzy` flag
        THEN none carries it, because `makemessages` guesses a translation
             from a similar msgid and marks it fuzzy: gettext then IGNORES it
             at runtime while every "is it filled?" check reads it as done —
             `Respondents open here — centre` was handed the translation of
             `Respondents will open the map exactly like this` this way
        """
        import pathlib

        from django.conf import settings as dj_conf

        # The header entry legitimately carries `#, fuzzy` — it is msgid "".
        fuzzy = re.compile(
            r'^#, [^\n]*fuzzy[^\n]*\n(?:^#[^\n]*\n)*^msgid "(?P<id>[^"]+)"',
            re.M)

        locales = pathlib.Path(__file__).resolve().parent.parent / 'locale'
        offenders = []
        for code, _name in dj_conf.LANGUAGES:
            if code == dj_conf.LANGUAGE_CODE:
                continue
            catalog = locales / code / 'LC_MESSAGES' / 'django.po'
            if not catalog.exists():
                continue
            offenders += [
                f'{code}: {match.group("id")[:60]!r}'
                for match in fuzzy.finditer(
                    catalog.read_text(encoding='utf-8'))]

        self.assertEqual(
            offenders, [],
            'Fuzzy entry — review the guess and drop the flag:\n  '
            + '\n  '.join(offenders))


class RespondentCatalogTest(TestCase):
    """Every interface string a respondent sees is translated in all 75 catalogs.

    Spec `ui-internationalization`, change respondent-strings-i18n (#385). The
    creator-side guard above matches template paths in the offered languages;
    a respondent reads one of 75, and strings added since the last bulk pass
    (the icon grid's "Show all options", the tap-to-place hint, the safety
    footer) shipped in English to a Portuguese school survey. So this test
    records what gettext is actually asked for while an anonymous visitor
    walks the respondent pages: Python strings handed to JS count, the signed-in
    account menu in `base.html` does not.

    It reads the compiled `.mo` files through the stdlib, which is what runs:
    a fuzzy `.po` entry never reaches them.
    """

    FEATURE_SURVEY = {
        "name": "i18n_respondent_fixture",
        "organization": "i18n fixture",
        "available_languages": ["pt", "en"],
        "redirect_url": "#",
        "sections": [
            {"name": "s_tap", "title": "Tap", "code": "s_tap", "is_head": True,
             "layout": "map", "next_section_name": "s_geo", "prev_section_name": None,
             "questions": [{
                 "code": "TAP_POINT", "order_number": 0, "name": "Place",
                 "input_type": "point", "tap_to_place": True,
                 "sub_question_groups": [
                     {"code": "TAP_G", "title": "", "display_style": "collapsible",
                      "order_number": 1, "translations": []},
                 ],
                 "sub_questions": [
                     {"code": "TAP_KIND", "order_number": 0, "name": "Kind",
                      "input_type": "choice", "display_style": "icon_grid",
                      "choices": [
                          {"code": 1, "name": "Park", "icon": "maki:park", "group": "Green"},
                          {"code": 2, "name": "Shop", "icon": "fas fa-coffee", "group": "Town"},
                      ]},
                     {"code": "TAP_KNOW", "order_number": 2, "name": "Know it?",
                      "input_type": "thumbs", "group": "TAP_G",
                      "choices": [{"code": 1, "name": "up"}, {"code": 0, "name": "down"}]},
                     {"code": "TAP_WHEN", "order_number": 3, "name": "When?",
                      "input_type": "multichoice", "group": "TAP_G",
                      "choices": [{"code": 1, "name": "Morning"},
                                  {"code": 2, "name": "Other", "other": True}]},
                 ],
             }]},
            {"name": "s_geo", "title": "Geo", "code": "s_geo", "is_head": False,
             "layout": "map", "next_section_name": "s_form", "prev_section_name": "s_tap",
             "questions": [
                 {"code": "GEO_POINT", "order_number": 0, "name": "Point", "input_type": "point"},
                 {"code": "GEO_LINE", "order_number": 1, "name": "Line", "input_type": "line"},
                 {"code": "GEO_POLY", "order_number": 2, "name": "Area", "input_type": "polygon"},
                 {"code": "GEO_SPRAY", "order_number": 3, "name": "Spray", "input_type": "spraycan",
                  "spray_brush": "medium"},
             ]},
            {"name": "s_form", "title": "Form", "code": "s_form", "is_head": False,
             "layout": "form", "next_section_name": None, "prev_section_name": "s_geo",
             "groups": [{"code": "FORM_G", "title": "", "display_style": "collapsible",
                         "order_number": 0, "translations": []}],
             "questions": [
                 {"code": "F_TEXT", "order_number": 1, "name": "Why?", "input_type": "text",
                  "required": True, "group": "FORM_G"},
                 {"code": "F_LINE", "order_number": 2, "name": "Name", "input_type": "text_line",
                  "group": "FORM_G"},
                 {"code": "F_NUM", "order_number": 3, "name": "Age", "input_type": "number"},
                 {"code": "F_CHOICE", "order_number": 4, "name": "One", "input_type": "choice",
                  "choices": [{"code": 1, "name": "A"}, {"code": 2, "name": "Other", "other": True}]},
                 {"code": "F_DROP", "order_number": 5, "name": "Drop", "input_type": "choice",
                  "display_style": "dropdown", "choices": [{"code": 1, "name": "A"}]},
                 {"code": "F_MULTI", "order_number": 6, "name": "Many", "input_type": "multichoice",
                  "choices": [{"code": 1, "name": "A"}, {"code": 2, "name": "B"}]},
                 {"code": "F_RATE", "order_number": 7, "name": "Rate", "input_type": "rating",
                  "choices": [{"code": i, "name": str(i)} for i in range(1, 6)]},
                 {"code": "F_RANGE", "order_number": 8, "name": "Range", "input_type": "range",
                  "choices": [{"code": 1, "name": "Low"}, {"code": 2, "name": "High"}]},
                 {"code": "F_RANK", "order_number": 9, "name": "Rank", "input_type": "ranking",
                  "choices": [{"code": 1, "name": "A"}, {"code": 2, "name": "B"}]},
                 {"code": "F_DATE", "order_number": 10, "name": "When", "input_type": "datetime"},
                 {"code": "F_THUMB", "order_number": 11, "name": "Like?", "input_type": "thumbs",
                  "choices": [{"code": 1, "name": "up"}, {"code": 0, "name": "down"}]},
                 {"code": "F_PHOTO", "order_number": 12, "name": "Photo", "input_type": "photo"},
                 {"code": "F_AUDIO", "order_number": 13, "name": "Audio", "input_type": "audio"},
                 {"code": "F_DOC", "order_number": 14, "name": "File", "input_type": "document"},
                 {"code": "F_HTML", "order_number": 15, "name": "Note", "input_type": "html",
                  "subtext": "<p>Hello</p>"},
             ]},
        ],
    }

    @classmethod
    def _catalogs(cls):
        """{language: set of msgids its compiled catalog translates}."""
        import gettext as stdlib_gettext
        import pathlib

        locales = pathlib.Path(__file__).resolve().parent.parent / 'locale'
        catalogs = {}
        for mo in sorted(locales.glob('*/LC_MESSAGES/django.mo')):
            with mo.open('rb') as fh:
                translations = stdlib_gettext.GNUTranslations(fh)
            # Plural entries are keyed (msgid, index); the header is msgid "".
            catalogs[mo.parent.parent.name] = {
                (key[0] if isinstance(key, tuple) else key)
                for key, value in translations._catalog.items()
                if key and key != ('', 0) and value}
        return catalogs

    @staticmethod
    def _is_ours(msgids):
        """The msgids that belong to this project rather than Django or a
        third-party app: named in one of our `.po` files (filled or not), or
        written literally in our templates or Python. A string nobody ran
        `makemessages` for is in no catalog at all, which is the case this
        test exists for, so the catalogs alone cannot define "ours"."""
        import pathlib

        root = pathlib.Path(__file__).resolve().parent.parent.parent
        po_ids = set()
        for po in (root / 'survey' / 'locale').glob('*/LC_MESSAGES/django.po'):
            po_ids.update(
                m.encode('latin-1', 'backslashreplace').decode('unicode_escape')
                if '\\' in m else m
                for m in re.findall(r'^msgid(?:_plural)? "(.+)"$',
                                    po.read_text(encoding='utf-8'), re.M))
        sources = []
        for app in ('survey', 'billing', 'mapsurvey'):
            for path in (root / app).rglob('*'):
                if path.suffix in ('.html', '.py', '.txt') and 'locale' not in path.parts \
                        and path.name != 'tests.py' and 'tests' not in path.parts:
                    sources.append(path.read_text(encoding='utf-8', errors='ignore'))
        source = '\n'.join(sources)
        return {m for m in msgids if m in po_ids or m in source}

    def _import_fixture(self):
        from survey.serialization import import_survey_from_zip

        buf = BytesIO()
        with zipfile.ZipFile(buf, 'w') as zf:
            zf.writestr('survey.json', json.dumps(
                {"version": "1.0", "mode": "structure", "survey": self.FEATURE_SURVEY}))
        buf.seek(0)
        survey, warnings = import_survey_from_zip(buf)
        self.assertEqual(warnings, [])
        survey.status = 'published'
        survey.save(update_fields=['status'])
        return survey

    def _walk_respondent_pages(self, survey):
        """GET/POST every respondent surface; return the msgids gettext was asked for."""
        seen = set()
        real = translation._trans

        def recorder(name, key):
            original = getattr(real, name)

            def wrapper(*args):
                seen.add(key(args))
                return original(*args)
            return wrapper

        # The `_trans` proxy caches each function on first use, so patch the
        # attribute itself; every translation.gettext()/{% trans %} goes through it.
        patches = [
            patch.object(real, 'gettext', recorder('gettext', lambda a: a[0])),
            patch.object(real, 'ngettext', recorder('ngettext', lambda a: a[0])),
            patch.object(real, 'pgettext', recorder('pgettext', lambda a: f'{a[0]}\x04{a[1]}')),
            patch.object(real, 'npgettext', recorder('npgettext', lambda a: f'{a[0]}\x04{a[1]}')),
        ]
        client = Client()
        base = f'/surveys/{survey.uuid}'
        with contextlib.ExitStack() as stack:
            for p in patches:
                stack.enter_context(p)
            pages = [
                client.get(f'{base}/language/'),
                client.post(f'{base}/language/', {'language': 'pt'}),
                client.get(f'{base}/s_tap/'),
                client.get(f'{base}/s_geo/'),
                client.get(f'{base}/s_form/'),
                # Required text left empty: the validation summary renders.
                client.post(f'{base}/s_form/', {}),
                client.get(f'{base}/thanks/'),
                client.get(f'{base}/report/'),
                client.post(f'{base}/report/', {}),
            ]
        for response in pages:
            self.assertIn(response.status_code, (200, 302), response)
        return seen

    def test_every_respondent_string_is_translated_in_every_catalog(self):
        """
        GIVEN a published survey in two languages that uses every question type,
              a tap-to-place point with an icon-grid choice, collapsible groups
              and every geo tool
        WHEN an anonymous visitor walks the language choice, each section, a
             failed required answer, the thanks page and the report form
        THEN every msgid of ours that gettext was asked for is translated in all
             75 catalogs, because a respondent reads whichever one the creator
             picked and a missing entry renders English in the middle of it
        """
        catalogs = self._catalogs()
        self.assertEqual(len(catalogs), 75)
        seen = self._walk_respondent_pages(self._import_fixture())

        self.assertIn('Show all options', seen)   # the walk reached the icon grid
        missing = {}
        for msgid in sorted(self._is_ours(seen)):
            langs = sorted(code for code, ids in catalogs.items()
                           if code != 'en' and msgid not in ids)
            if langs:
                missing[msgid] = langs
        self.assertEqual(
            missing, {},
            'Respondent string untranslated:\n  ' + '\n  '.join(
                f'{m[:70]!r}: {len(l)} languages ({", ".join(l[:8])}…)'
                for m, l in missing.items()))


class EditorJsNumberLocaleTest(TestCase):
    """Numbers the editor writes into JavaScript must not be locale-formatted.

    `USE_L10N` is on and every one of the ten non-English languages in
    `LANGUAGES` -- de, fr, es, pt, pl, id, nl, it, et, fi -- writes decimals
    with a comma, so an unguarded coordinate renders as `52,5231` and
    the surrounding `<script>` stops being JavaScript -- the map picker never
    initialises for a creator working in anything but English. PostHog logged
    this as three separate htmx issues, because htmx evaluates the scripts it
    swaps in and its frames sit on top of the stack: "Unexpected token ','.
    Expected ':' in ternary operator." names the exact construct, and
    "Unexpected number '52'" names the leading digits of our Berlin default.

    The respondent side has been guarded since before the editor was written
    (`{% localize off %}` in base_survey_template.html), which is why this test
    checks the editor's templates specifically.

    Getting the page into Russian at all took two tries: `translation.override`
    is discarded by `LocaleMiddleware`, which re-activates per request, and
    `Accept-Language` loses to the language cookie that `login()` has already
    written. Both versions passed against the unfixed templates.
    """

    # A comma between two digits inside a script block: no hand-written JS
    # produces that, and these templates carry no JSON blobs where `[1,2]`
    # would be legitimate.
    DECIMAL_COMMA = re.compile(r'\d,\d')
    SCRIPT = re.compile(r'<script\b[^>]*>(.*?)</script>', re.S | re.I)

    def setUp(self):
        self.user = User.objects.create_user(username='locale_owner', password='pass')
        self.org = _make_org('LocaleOrg')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.survey = SurveyHeader.objects.create(
            name='locale_survey', organization=self.org,
            start_map_postion=Point(13.4050, 52.5231), start_map_zoom=12,
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='sec', code='S1', is_head=True,
            start_map_postion=Point(13.3777, 52.5163), start_map_zoom=14,
        )
        self.client.login(username='locale_owner', password='pass')
        session = self.client.session
        session['active_org_id'] = self.org.id
        session.save()
        # The creator's UI language lives in the language COOKIE, written by
        # CreatorLanguageCookieMiddleware from their saved preference; login()
        # above already set it to `en`. Neither Accept-Language nor
        # translation.override can beat a cookie that is already there, so the
        # cookie is the only honest way to put these pages into Russian --
        # written either of the other two ways, these tests pass against the
        # unfixed templates.
        self._use_language('de')

    def _use_language(self, code):
        from django.conf import settings as _s
        self.client.cookies[_s.LANGUAGE_COOKIE_NAME] = code

    def _scripts(self, html):
        return '\n'.join(self.SCRIPT.findall(html))

    def _assert_no_localized_decimal(self, html, where):
        scripts = self._scripts(html)
        found = self.DECIMAL_COMMA.search(scripts)
        self.assertIsNone(
            found,
            f"{where}: a locale-formatted number reached JavaScript "
            f"({scripts[max(0, found.start() - 60):found.start() + 40] if found else ''!r})",
        )

    def test_layer_object_editor_has_no_localized_decimals(self):
        """
        GIVEN a survey with float coordinates
        WHEN the layer object editor renders under a comma-decimal UI language
        THEN no digit-comma-digit sequence appears in any script block

        The page the August 2026 fix did not cover: it was written a week later
        and reintroduced the defect, unguarded, for six weeks.
        """
        from survey.models import SurveyMapLayer
        layer = SurveyMapLayer.objects.create(
            survey=self.survey, name='Stops', geojson='', position=1)
        response = self.client.get(
            f'/editor/surveys/{self.survey.uuid}/layers/{layer.id}/edit/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get('Content-Language'), 'de')
        self._assert_no_localized_decimal(response.content.decode(), 'layer object editor')

    def test_coordinates_are_identical_in_both_locales(self):
        """
        GIVEN the same survey
        WHEN the settings page renders under English and under German
        THEN the coordinates in the script are byte-identical

        Guards against a fix that merely removes commas — the numbers have to
        be the same numbers, with a decimal point, in both languages.
        """
        url = f'/editor/surveys/{self.survey.uuid}/settings/'
        self._use_language('en')
        en = self._scripts(self.client.get(url).content.decode())
        self._use_language('de')
        ru = self._scripts(self.client.get(url).content.decode())
        for needle in ('52.5231', '13.405'):
            self.assertIn(needle, en)
            self.assertIn(needle, ru)

    def test_guard_would_catch_a_localized_decimal(self):
        """
        GIVEN a template line of the shape this bug produced
        WHEN rendered under a comma-decimal locale without the guard
        THEN the detector fires

        Pins the detector itself: without this, a regex that never matches
        anything would make the tests above pass forever.
        """
        unguarded = Template('<script>var lat = a ? {{ y }} : b;</script>')
        with translation.override('de'):
            rendered = unguarded.render(Context({'y': 52.5231}))
        self.assertRegex(self._scripts(rendered), self.DECIMAL_COMMA)


class TemplateScriptLocalizationGuardTest(SimpleTestCase):
    """No template may write an unguarded server-side value into JavaScript.

    This is the class-level guard. The rendering tests above prove that specific
    pages are correct today; this one fails when a NEW template gets it wrong,
    which is the failure mode that actually happened. The August 2026 fix
    guarded three templates and pinned its tests to two URLs, so the map
    template added six days later (#155) shipped the same defect green. It ran
    in production for six weeks, and every exception it produced came from a
    creator working in German, Dutch or Polish -- none from English.

    It scans template SOURCE rather than rendered pages for the same reason
    ExternalScriptCorsTest does: a rendering test can only assert about URLs
    someone remembered to list, and the whole defect is that nobody remembers.

    Django localizes a float under an active locale, so ten of the eleven
    shipped creator languages turn 52.5231 into `52,5231`. Inside JavaScript
    that is either a syntax error or -- with a thousands separator -- a silently
    different number.
    """

    TEMPLATE_DIR = os.path.join(settings.BASE_DIR, 'survey', 'templates')

    SCRIPT = re.compile(r'<script\b(?P<attrs>[^>]*)>(?P<body>.*?)</script>', re.S | re.I)
    TYPE_ATTR = re.compile(r'type\s*=\s*[\'"]([^\'"]+)[\'"]', re.I)
    VAR = re.compile(r'\{\{\s*(?P<expr>.*?)\s*\}\}', re.S)
    LOCALIZE_OFF = re.compile(r'\{%\s*localize\s+off\s*%\}(.*?)\{%\s*endlocalize\s*%\}', re.S)
    INCLUDE = re.compile(r'\{%\s*include\s+[\'"]([^\'"]+)[\'"]')

    # A filter that yields a string or pre-serialized JSON cannot be reformatted
    # by the locale; `unlocalize` is the per-value guard.
    SAFE_FILTERS = ('unlocalize', '|safe', 'json_script', '|escapejs', '|yesno')

    @staticmethod
    def _inside_string(prefix):
        """Is the interpolation point inside a JavaScript string literal?

        `= '{{ x }}'` is a string literal: a comma inside it cannot change how
        the script parses. This counts unescaped quotes rather than matching a
        pattern -- a regex looking for "a quote, then no quotes to the end"
        happily anchors on the CLOSING quote of an earlier literal, which is
        how the first version of this guard passed against the very line it was
        written to catch:

            var map = L.map('loe-map', {...}).setView([{{ lat }}, ...
                            ^ closing quote here, rest of the line quote-free
        """
        quote, escaped = None, False
        for ch in prefix:
            if escaped:
                escaped = False
            elif ch == '\\':
                escaped = True
            elif quote:
                if ch == quote:
                    quote = None
            elif ch in '"\'`':
                quote = ch
        return quote is not None

    def _templates(self):
        for root, _dirs, files in os.walk(self.TEMPLATE_DIR):
            for filename in files:
                if filename.endswith('.html'):
                    yield os.path.join(root, filename)

    def _partials_included_inside_scripts(self):
        """Templates that are `{% include %}`d from inside a <script> block.

        `partials/basemap_layers.html` is bare JavaScript with no script tag of
        its own, so scanning for <script> alone would never look at it. Deriving
        the set from actual include sites beats an allow-list that drifts, and
        beats guessing from "the file has no HTML tags" -- which misreads a
        plain-text email body as JavaScript.
        """
        included = set()
        for path in self._templates():
            with open(path, encoding='utf-8') as fh:
                body = fh.read()
            for match in self.SCRIPT.finditer(body):
                for inc in self.INCLUDE.finditer(match.group('body')):
                    included.add(inc.group(1))
        return included

    def _js_blocks(self, path, body, script_partials):
        """Yield (offset, text) for every JavaScript region of one template."""
        rel = os.path.relpath(path, self.TEMPLATE_DIR).replace(os.sep, '/')
        if rel in script_partials:
            yield 0, body
            return
        for match in self.SCRIPT.finditer(body):
            declared = self.TYPE_ATTR.search(match.group('attrs'))
            # `application/json` and `text/plain` islands are data read by other
            # code, not parsed as JavaScript.
            if declared and 'javascript' not in declared.group(1).lower():
                continue
            yield match.start('body'), match.group('body')

    def _offenders(self):
        script_partials = self._partials_included_inside_scripts()
        for path in self._templates():
            with open(path, encoding='utf-8') as fh:
                body = fh.read()
            for offset, block in self._js_blocks(path, body, script_partials):
                guarded = [(m.start(1), m.end(1)) for m in self.LOCALIZE_OFF.finditer(block)]
                for var in self.VAR.finditer(block):
                    if any(a <= var.start() < b for a, b in guarded):
                        continue
                    expr = var.group('expr')
                    if any(f in expr for f in self.SAFE_FILTERS):
                        continue
                    line_start = block.rfind('\n', 0, var.start()) + 1
                    if self._inside_string(block[line_start:var.start()]):
                        continue
                    line = body.count('\n', 0, offset + var.start()) + 1
                    rel = os.path.relpath(path, self.TEMPLATE_DIR)
                    yield '%s:%d  {{ %s }}' % (rel, line, expr)

    def _scan(self, source):
        """Run the scanner over one template body held in a temporary tree."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, 'probe.html'), 'w', encoding='utf-8') as fh:
                fh.write(source)
            with mock.patch.object(type(self), 'TEMPLATE_DIR', tmp):
                return list(self._offenders())

    def test_no_unguarded_interpolation_reaches_javascript(self):
        """
        GIVEN every template shipped under survey/templates
        WHEN each JavaScript region is scanned for server-side interpolation
        THEN every bare value is inside {% localize off %} or filtered through |unlocalize
        """
        offenders = sorted(self._offenders())
        self.assertEqual(
            offenders, [],
            'A locale-formatted value can reach JavaScript here. Wrap the block in '
            '{% localize off %} (preferred -- it also covers a value added later) or '
            'filter the value through |unlocalize:\n  ' + '\n  '.join(offenders),
        )

    def test_the_scanner_sees_script_only_partials(self):
        """
        GIVEN a partial that is bare JavaScript with no <script> tag of its own
        WHEN the set of script-included partials is derived from include sites
        THEN that partial is in it

        Without this the scanner would silently skip the basemap partial, and a
        coordinate added there would never be checked.
        """
        self.assertIn('partials/basemap_layers.html',
                      self._partials_included_inside_scripts())

    def test_the_scanner_can_fail(self):
        """
        GIVEN a template body of the shape this defect produced
        WHEN it is scanned
        THEN an offender is reported

        Pins the detector: a regex that matched nothing would make the test
        above pass forever. The August fix recorded three green-on-broken
        versions of its own tests.
        """
        self.assertTrue(
            self._scan('<script>var lat = {{ survey.start_map_postion.y }};</script>'))

    def test_the_scanner_accepts_a_guarded_block(self):
        """
        GIVEN the same body wrapped in {% localize off %}
        WHEN it is scanned
        THEN nothing is reported
        """
        self.assertEqual(self._scan(
            '<script>{% localize off %}'
            'var lat = {{ survey.start_map_postion.y }};{% endlocalize %}</script>'), [])

    def test_the_scanner_ignores_a_quoted_value(self):
        """
        GIVEN an interpolation inside a JavaScript string literal
        WHEN it is scanned
        THEN it is not reported, because a comma there cannot change parsing
        """
        self.assertEqual(
            self._scan("<script>var u = '{{ MAPBOX_URL }}';</script>"), [])

    def test_the_scanner_ignores_a_json_data_island(self):
        """
        GIVEN a <script type="application/json"> block carrying serialized data
        WHEN it is scanned
        THEN it is not reported, because nothing parses it as JavaScript
        """
        self.assertEqual(self._scan(
            '<script type="application/json" id="d">{{ counts }}</script>'), [])
