"""Live numbers in a story's text (change reports-live-blocks, #704; Vision FE-7).

A figure in the narrative may be a token instead of typed digits: it is filled from the report's
home survey when the page is rendered, so it follows new answers while the report is live and is
fixed in a frozen one (the snapshot stores the filled text). Typed numbers stay allowed.

    {responses}          people who answered (the number every public surface prints)
    {opened} {finished}  the other two steps of the engagement funnel
    {marks:CODE}         marks placed on the map question CODE
    {respondents:CODE}   people who answered question CODE

Every value goes through `data.aggregate.mask` with the report's K: a count under K reads "<K".
A token the report cannot fill — no home survey, an unknown code — is left as written, so the
author sees it on the page instead of a silent zero.
"""
import re

from data.aggregate import mask

TOKEN = re.compile(r'\{(responses|opened|answered|finished)\}|\{(marks|respondents):([A-Za-z0-9_\-]{1,50})\}')
HELP = ('{responses}', '{opened}', '{finished}', '{marks:CODE}', '{respondents:CODE}')


class Tokens:
    """The values of one render, computed on first use and once."""

    def __init__(self, survey, k):
        self.survey, self.k = survey, max(1, int(k or 1))
        self._steps = None
        self._questions = {}

    def _step(self, key):
        if self._steps is None:
            from data.analysis import engagement
            self._steps = {s['key']: s['display'] for s in engagement(self.survey, self.k)['steps']}
        return self._steps.get('answered' if key == 'responses' else key)

    def _question(self, code):
        """(marks, respondents) of a question's lineage in the public scope, or None."""
        if code not in self._questions:
            from data.questions import question_of
            from data.scope import SessionScope
            from survey.models import Answer
            from survey.versioning import family_ids
            question = question_of(self.survey, code)
            counts = None
            if question is not None:
                rows = (Answer.objects
                        .filter(question__code=code, question__input_type=question.input_type,
                                question__survey_section__survey_header_id__in=family_ids(self.survey))
                        .filter(SessionScope.public(self.survey).q('survey_session')))
                counts = (rows.count(), rows.values('survey_session_id').distinct().count())
            self._questions[code] = counts
        return self._questions[code]

    def value(self, match):
        if self.survey is None:
            return match.group(0)
        if match.group(1):
            return self._step(match.group(1)) or match.group(0)
        counts = self._question(match.group(3))
        if counts is None:
            return match.group(0)
        return mask(counts[0] if match.group(2) == 'marks' else counts[1], self.k)['display']

    def fill(self, text):
        """`text` with its tokens replaced. Values are digits or "<K": safe in HTML and in text."""
        if not text or '{' not in text:
            return text
        return TOKEN.sub(lambda m: self.value(m).replace('<', '&lt;'), text)

    def fill_plain(self, text):
        """For a value the template escapes itself (a key number, the opening paragraph)."""
        if not text or '{' not in text:
            return text
        return TOKEN.sub(self.value, text)
