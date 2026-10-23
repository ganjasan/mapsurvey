"""What the OpenAPI document says about errors.

Every operation carries the envelope for each status it can answer and
`x-error-codes`, the stable codes a client may switch on -- the generated
reference lists them, and `test_v1_contract` checks that their union is
`api.errors.ALL_CODES`.
"""
from .. import errors as e

ENVELOPE = {
    'type': 'object',
    'required': ['error', 'detail'],
    'properties': {
        'error': {'type': 'string', 'enum': list(e.ALL_CODES)},
        'detail': {'type': 'string'},
        'fields': {'type': 'object', 'additionalProperties': {'type': 'array', 'items': {'type': 'string'}},
                   'description': 'validation: field name → messages'},
    },
    'additionalProperties': True,
}

ALWAYS = {
    401: (e.INVALID_TOKEN,),
    403: (e.SCOPE_MISSING, e.PRO_REQUIRED, e.FORBIDDEN_ROLE),
    404: (e.NOT_FOUND,),
    405: (e.METHOD_NOT_ALLOWED,),
    422: (e.VALIDATION,),
    429: (e.RATE_LIMITED,),
    500: (e.SERVER_ERROR,),
}

DESCRIPTIONS = {
    400: 'Bad request', 401: 'Missing or invalid bearer token', 403: 'Forbidden',
    404: 'Not found', 405: 'Method not allowed', 409: 'Conflict', 422: 'Invalid input', 429: 'Rate limited', 500: 'Server error',
}

STATUS_OF = {
    e.DRAFT_REQUIRED: 409, e.ANSWERS_AT_RISK: 409, e.DELETE_BLOCKED: 409, e.TRANSLATION_GAPS: 409,
    e.INCOMPATIBLE_DRAFT: 409, e.TRANSITION_REFUSED: 409, e.CONFLICT: 409, e.BAD_CURSOR: 400,
}


def errors(*extra_statuses, codes=()):
    """`openapi_extra` for an operation: the always-possible errors plus
    `codes` (and `draft_required` whenever 409 is named)."""
    by_status = {status: list(c) for status, c in ALWAYS.items()}
    wanted = list(codes)
    if 409 in extra_statuses and e.DRAFT_REQUIRED not in wanted:
        wanted.append(e.DRAFT_REQUIRED)
    for code in wanted:
        by_status.setdefault(STATUS_OF[code], []).append(code)
    for status in extra_statuses:
        by_status.setdefault(status, [])
    responses = {
        str(status): {
            'description': f'{DESCRIPTIONS[status]}: ' + ', '.join(c) if c else DESCRIPTIONS[status],
            'content': {'application/json': {'schema': ENVELOPE}},
        }
        for status, c in sorted(by_status.items())
    }
    return {'responses': responses,
            'x-error-codes': sorted({c for cs in by_status.values() for c in cs})}


def list_errors():
    return errors(codes=(e.BAD_CURSOR,))
