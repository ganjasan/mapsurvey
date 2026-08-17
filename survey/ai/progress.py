"""How much of a draft has actually arrived, counted from the draft itself.

Deliberately free of HTTP, Django and provider specifics: this is the one
genuinely fiddly piece of the streaming path, and it should be testable by
handing it strings.

The count is structural, not textual. Counting a marker substring ("how many
times does `questions` appear") counts creator-visible label text as readily as
structure, and a progress indicator that counts the words in someone's survey is
worse than no indicator at all — it is the fabricated-stage problem the create
overlay has always refused, wearing a number.

`survey_draft_schema` pins the shape this relies on: the root object has exactly
one key (`sections`), whose items each carry a `questions` array. So an object
closing at a known nesting path is unambiguous. Sub-question, option and
localized-text objects all close deeper than the two paths below and cannot be
mistaken for either.
"""

# The container stack, at the moment a `}` is seen, for an object that is:
_SECTION_PATH = ('{', '[', '{')                 # an element of root.sections
_QUESTION_PATH = ('{', '[', '{', '[', '{')      # an element of a section's questions


class DraftProgress:
    """Incremental scanner over the accumulated draft text.

    Fed each chunk as it arrives and never rescanning what it has already seen,
    so the cost is linear in the draft rather than quadratic in the number of
    chunks.

    Counts only what has *closed*. A section half-written when the stream is
    still going is not a section the model has produced, and reporting it would
    make the number jump backwards if the stream then failed.
    """

    def __init__(self):
        self._stack = []
        self._in_string = False
        self._escaped = False
        self.sections = 0
        self.questions = 0

    def feed(self, text):
        """Consume the next chunk. Returns True if either count advanced."""
        before = (self.sections, self.questions)
        for ch in text:
            if self._in_string:
                # Inside a string literal nothing is structure: a creator's
                # question label may contain braces, quotes and backslashes, and
                # every one of them would otherwise shift the nesting path.
                if self._escaped:
                    self._escaped = False
                elif ch == '\\':
                    self._escaped = True
                elif ch == '"':
                    self._in_string = False
                continue
            if ch == '"':
                self._in_string = True
            elif ch in '{[':
                self._stack.append(ch)
            elif ch in '}]':
                if not self._stack:
                    # More closes than opens can only come from a truncated or
                    # corrupt stream. Ignore it: this counter must never be the
                    # reason a draft fails.
                    continue
                path = tuple(self._stack)
                self._stack.pop()
                if ch == '}':
                    if path == _SECTION_PATH:
                        self.sections += 1
                    elif path == _QUESTION_PATH:
                        self.questions += 1
        return (self.sections, self.questions) != before
