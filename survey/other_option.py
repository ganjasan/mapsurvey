"""The "Other, please specify" write-in option (openspec: other-option-write-in).

A ``choice``/``multichoice`` question may flag ONE option with ``{"other": true}``. When a
respondent selects it, a text input named ``<code>-other`` travels with the form and its
value lands in ``Answer.text`` of the SAME row that holds ``selected_choices`` -- the
column is unused by choice answers otherwise. Everything that decides what that means
lives here, so the three storage sites and the read surfaces never re-derive the rule.

Privacy boundary: ``public_results`` and ``object_stats`` deliberately do not import
this module. They keep reading ``selected_choices`` only, so the text never reaches
respondents or the public page.
"""

WRITE_IN_TYPES = ('choice', 'multichoice')

# A hyphen, on purpose: it survives the `rsplit('__', 1)` that splits
# `obj__<key>__<code>` fields and the unquoted `[name=<key>]` selector the geo popup
# restore uses (a colon there is a jQuery syntax error). Codes are `Q_<digits>`, so the
# suffix can never collide with a real question code.
OTHER_FIELD_SUFFIX = '-other'


def field_name(question_code):
    """Name of the write-in input that accompanies question ``question_code``."""
    return f'{question_code}{OTHER_FIELD_SUFFIX}'


def is_other_field(name):
    return str(name).endswith(OTHER_FIELD_SUFFIX)


def base_code(name):
    """``Q_1-other`` -> ``Q_1``; any other name unchanged."""
    return name[:-len(OTHER_FIELD_SUFFIX)] if is_other_field(name) else name


def other_code(question):
    """Code of the flagged option, or None.

    First match wins, so a stray double flag (an old ZIP, a hand-edited row) behaves as
    one option, never two. Types other than choice/multichoice never have one, whatever
    their stored choices say.
    """
    if getattr(question, 'input_type', None) not in WRITE_IN_TYPES:
        return None
    for choice in question.choices or []:
        if isinstance(choice, dict) and choice.get('other'):
            return choice.get('code')
    return None


def other_text(question, selected_codes, raw):
    """What to store in ``Answer.text`` for this selection.

    The posted text (empty allowed -- the option itself is the answer) when the flagged
    option is among ``selected_codes``; None otherwise, so text a client posted for an
    option it did not select is discarded, never stored.
    """
    code = other_code(question)
    if code is None or code not in (selected_codes or []):
        return None
    return (raw or '').strip()


def clamp_single_other(choices):
    """Keep the first ``other: true``, drop the flag from the rest. Mutates and returns."""
    seen = False
    for choice in choices or []:
        if not isinstance(choice, dict) or not choice.get('other'):
            continue
        if seen:
            del choice['other']
        seen = True
    return choices


def answer_text(answer):
    """The write-in of a choice answer, or None when the flagged option is not selected."""
    code = other_code(answer.question)
    if code is None or code not in (answer.selected_choices or []):
        return None
    return answer.text if answer.text is not None else ''


def display(answer, lang=None, separator=', '):
    """``"A, Other: text"`` -- the selected labels, the flagged one followed by its text.

    For the creator's eyes (Responses table, drawer, map attributes). Not for the public
    page, which must keep calling ``get_choice_name`` on codes alone.
    """
    question = answer.question
    code = other_code(question)
    text = answer_text(answer)
    parts = []
    for selected in answer.selected_choices or []:
        label = question.get_choice_name(selected, lang)
        if selected == code and text:
            label = f'{label}: {text}'
        parts.append(label)
    return separator.join(parts)


def export_column(question, lang=None):
    """Header of the adjacent export column, or None when the question has no write-in."""
    code = other_code(question)
    if code is None:
        return None
    return f'{question.name}: {question.get_choice_name(code, lang)}'


def export_cell(question, answer, base):
    """``base`` unchanged for a question without a write-in option.

    Otherwise the dict shape the export loops merge (the one ``ranking`` already returns):
    the question's own column keeps ``base`` and the adjacent column holds the text. The
    adjacent key is present on EVERY row of the question, empty when the option was not
    picked: pandas orders CSV columns by first appearance, and a column that only exists on
    some rows would drift away from its question.
    """
    column = export_column(question)
    if column is None:
        return base
    text = answer_text(answer) if answer is not None else None
    return {question.name: base, column: text or ''}
