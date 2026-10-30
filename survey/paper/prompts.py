"""What the model is told when it reads a photographed page (design D5).

Literal text, one place. The user message is built by `extract.py` from the
items printed on the page; this module holds the rules of reading and the
response schema. Content from the sheet never flows back into a prompt.
"""

SYSTEM = """You read one photographed page of a filled-in paper survey form and report the respondent's answers.

You are given the questions printed on this page, with a code, a type and, for choice questions, the options with their codes. Report one entry per question that is visible on the page. Skip questions you cannot see on this page.

Rules of reading:
- A checkbox is marked when it has any ink inside it — a tick, a cross, a dot, a scribble, a filled square. A struck-through or scribbled-out mark next to a clearly marked other box is not an answer.
- For a single-choice question report ONE option code: the marked one. If two boxes are marked and neither is struck through, report the first and set unreadable to true.
- For a multiple-choice question report every marked option code, in option order.
- For a ranking question report the option codes in the order of the numbers written in front of them.
- For a number, range or rating question report the number as digits (the marked box's label, or the handwritten number).
- For thumbs report "1" for the up/positive box, "0" for the down/negative box.
- For text questions transcribe the handwriting as written, in the language it is written in, keeping line breaks as spaces. Do not correct spelling. Do not summarise.
- For a date/time question transcribe what is written.
- An option flagged as write-in may have text on the line after it: report that text in the companion field named "<code>__other".
- When a question is left blank report value null with confidence 1.0 — blank is an answer you can be sure of.
- confidence is your honest probability, from 0 to 1, that the value is exactly what the respondent meant. Faint marks, two marks, ambiguous handwriting, a box half on a fold: lower it.
- unreadable is true when you cannot read the answer at all (torn, covered, illegible); value is then null.
- Never invent an answer. Never use an option code that is not in the list.
"""

RESPONSE_SCHEMA = {
    'type': 'object',
    'properties': {
        'fields': {
            'type': 'array',
            'items': {
                'type': 'object',
                'properties': {
                    'code': {'type': 'string', 'description': 'The question code, or <code>__other for a write-in text'},
                    'value': {
                        'description': 'The answer: an option code, a list of option codes, a number as text, '
                                       'a transcription, or null when blank or unreadable',
                        'anyOf': [
                            {'type': 'string'},
                            {'type': 'array', 'items': {'type': 'string'}},
                            {'type': 'null'},
                        ],
                    },
                    'confidence': {'type': 'number', 'minimum': 0, 'maximum': 1},
                    'unreadable': {'type': 'boolean'},
                },
                'required': ['code', 'value', 'confidence', 'unreadable'],
                'additionalProperties': False,
            },
        },
    },
    'required': ['fields'],
    'additionalProperties': False,
}

USER_HEAD = 'The questions printed on this page, in order. Report the answers you can read.\n'
USER_HEAD_WHOLE_FORM = (
    'The questions of the whole form, in order. This photo shows ONE of its pages: report only the '
    'questions that are visible on it and skip the rest.\n'
)
