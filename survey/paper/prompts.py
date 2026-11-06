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
- For a date/time question report the date as YYYY-MM-DD, and as YYYY-MM-DDTHH:MM (24-hour clock) when a time is written too. Handwritten dates are day/month/year unless only month/day/year makes sense; when both orders are possible (day and month both 12 or less) lower confidence. A two-digit year is in this century. When the writing cannot be read as a calendar date, report null with unreadable true.
- An option flagged as write-in may have text on the line after it: report that text in the companion field named "<code>__other".
- When a question is left blank report value null with confidence 1.0 — blank is an answer you can be sure of.
- confidence is your honest probability, from 0 to 1, that the value is exactly what the respondent meant. Faint marks, two marks, ambiguous handwriting, a box half on a fold: lower it.
- unreadable is true when you cannot read the answer at all (torn, covered, illegible); value is then null.
- Never invent an answer. Never use an option code that is not in the list.
- box is where the question is on the photo: [ymin, xmin, ymax, xmax], each 0–1000 as a fraction of the image height or width, covering the question's printed title and the respondent's answer to it. Report a box for every question you report, blank ones too.

Marks on the map (only when the message lists map questions): the page carries a printed map in a black rectangular frame. The respondent drew marks on it and wrote a letter and a number next to each (A1, A2, B1 …); the letter is the map question, the number is the row of that question's table below the map, where the respondent wrote the answers about that mark.
- map_frame is the box of the printed map's black frame: [ymin, xmin, ymax, xmax], 0–1000 of the photo.
- map_frame_corners are the four corners of that black frame as it appears on the photo, as [y, x] pairs 0–1000: top-left, top-right, bottom-left, bottom-right. A photo taken at an angle shows the frame as a trapezoid; give the actual corners of the black border, not of the box.
- Report one entry in marks per LABEL written on the map and per filled row of the table (A1, A2, …), whether or not you can make out the drawn mark itself: label (e.g. "A1"), question (the code of the map question with that letter), points — the mark's vertices as [y, x] pairs, 0–1000 of the photo: one point for a dot; the vertices along a drawn line in order; the corners of an outlined or shaded area in order around it — and confidence. If the drawn mark is unclear, leave points empty and still report the label, its label_box and the row's answers: the mark is read from the ink by other means, the row is not.
- points are the ink of the SYMBOL only — the centre of the drawn dot, the drawn line, the drawn outline. The letter and number written next to it are a label, never part of the mark: do not centre on them or include them.
- label_box is where that label is WRITTEN: the box around the handwritten letter and number, [ymin, xmin, ymax, xmax], 0–1000 of the photo. Omit it when nothing is written next to the mark.
- A mark without a legible label: still report it, with the letter of the question whose symbol it is (dot, line, area) and the next free number.
- answers are what is written in the mark's row of the table: one entry per column with the column's question code and the value, following the rules above for its type. Skip empty cells; an empty row is an empty list, never a missing field.
- Report nothing for the map when no mark is drawn on it; never invent a mark.
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
                    'box': {
                        'description': 'Where the question is on the photo: [ymin, xmin, ymax, xmax], 0-1000',
                        'type': 'array', 'items': {'type': 'integer'}, 'minItems': 4, 'maxItems': 4,
                    },
                },
                'required': ['code', 'value', 'confidence', 'unreadable'],
                'additionalProperties': False,
            },
        },
        'map_frame': {
            'description': 'The box of the printed map frame on the photo: [ymin, xmin, ymax, xmax], 0-1000',
            'type': 'array', 'items': {'type': 'integer'},
        },
        'map_frame_corners': {
            'description': 'The four corners of the printed map frame on the photo, [y, x] 0-1000: top-left, top-right, bottom-left, bottom-right',
            'type': 'array', 'items': {'type': 'array', 'items': {'type': 'number'}},
        },
        'marks': {
            'description': 'Every mark drawn on the printed map',
            'type': 'array',
            'items': {
                'type': 'object',
                'properties': {
                    'label': {'type': 'string', 'description': 'The letter and number written next to the mark, e.g. A1'},
                    'question': {'type': 'string', 'description': 'The code of the map question the letter stands for'},
                    'points': {
                        'description': 'The vertices of the mark as [y, x] pairs, 0-1000 of the photo',
                        'type': 'array', 'items': {'type': 'array', 'items': {'type': 'number'}},
                    },
                    'label_box': {
                        'description': 'The box around the handwritten label, [ymin, xmin, ymax, xmax], 0-1000 of the photo',
                        'type': 'array', 'items': {'type': 'number'},
                    },
                    'answers': {
                        'description': "What is written in the mark's row of the table",
                        'type': 'array',
                        'items': {
                            'type': 'object',
                            'properties': {
                                'code': {'type': 'string'},
                                'value': {'anyOf': [{'type': 'string'}, {'type': 'array', 'items': {'type': 'string'}}, {'type': 'null'}]},
                            },
                            'required': ['code', 'value'],
                        },
                    },
                    'confidence': {'type': 'number', 'minimum': 0, 'maximum': 1},
                },
                'required': ['label', 'question', 'answers', 'confidence'],
            },
        },
    },
    'required': ['fields'],
    'additionalProperties': False,
}

USER_MAP_HEAD = (
    '\nMap questions. The printed map on this page carries the marks of these questions; the letter '
    'is written next to each mark, the number is the row of the table below the map:\n'
)

USER_TABLE_HEAD = (
    '\nTable rows continued from another page. The map these marks are drawn on is NOT on this page; '
    'this page carries rows of its table (the marks table that started on the page before). Report every '
    'row with anything written in it as an entry in marks: its label, the question code given below, its '
    'answers — and no points.\n'
)

USER_HEAD = 'The questions printed on this page, in order. Report the answers you can read.\n'
USER_HEAD_WHOLE_FORM = (
    'The questions of the whole form, in order. This photo shows ONE of its pages: report only the '
    'questions that are visible on it and skip the rest.\n'
)
