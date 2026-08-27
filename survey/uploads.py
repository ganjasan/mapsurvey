"""Validation and limits for respondent file uploads.

Kept apart from the view so every rule is testable without HTTP. The view is
glue; the decisions live here.
"""

from django.utils.translation import gettext_lazy as _

# Platform ceiling. Creators can lower per question, never raise: audio at
# roughly a megabyte per minute is the sizing driver, and a 0.5-CPU instance
# has no business swallowing more than this in one request.
PLATFORM_MAX_BYTES = 25 * 1024 * 1024

# Per-session abuse caps: the endpoint is anonymous, so without these it is a
# free CDN. Counted over the session's uploads, attached or not.
SESSION_MAX_FILES = 30
SESSION_MAX_BYTES = 150 * 1024 * 1024

# Content-type allow-lists per input type. SVG is deliberately absent from the
# photo list: an SVG served from our bucket is a stored-XSS vector, and no
# respondent photographs anything in SVG.
ALLOWED_TYPES = {
    'photo': {
        'image/jpeg', 'image/png', 'image/webp', 'image/gif',
        'image/heic', 'image/heif',
    },
    'audio': {
        'audio/webm', 'audio/ogg', 'audio/mp4', 'audio/x-m4a', 'audio/m4a',
        'audio/mpeg', 'audio/mp3', 'audio/wav', 'audio/x-wav',
        # Recorder blobs sometimes arrive as video/* containers with audio-only
        # tracks (Safari's MediaRecorder in particular).
        'video/webm', 'video/mp4',
    },
    'document': {
        'application/pdf',
        'application/msword',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'application/vnd.ms-excel',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'application/vnd.oasis.opendocument.text',
        'application/vnd.oasis.opendocument.spreadsheet',
        'text/plain', 'text/csv',
    },
}

# Magic-byte checks where the format family makes them reliable. Audio
# containers vary too much for a byte-level check to be worth its false
# rejections; the allow-list plus the size cap bounds the damage there.
_MAGIC = {
    'image/jpeg': [b'\xff\xd8\xff'],
    'image/png': [b'\x89PNG\r\n\x1a\n'],
    'image/gif': [b'GIF87a', b'GIF89a'],
    'image/webp': [b'RIFF'],  # + 'WEBP' at offset 8, checked below
    'application/pdf': [b'%PDF-'],
}


class UploadRejected(Exception):
    """Respondent-readable refusal; `code` keeps the widget's error handling stable."""

    def __init__(self, code, message):
        self.code = code
        self.message = message
        super().__init__(message)


def effective_max_bytes(question):
    """The platform cap, lowered (never raised) by the creator's per-question cap."""
    vs = question.validation_settings or {}
    creator_cap = vs.get('max_file_bytes')
    if isinstance(creator_cap, (int, float)) and creator_cap > 0:
        return min(int(creator_cap), PLATFORM_MAX_BYTES)
    return PLATFORM_MAX_BYTES


def validate_upload(question, uploaded_file):
    """Raise UploadRejected unless the file is acceptable for this question."""
    allowed = ALLOWED_TYPES.get(question.input_type)
    if allowed is None:
        raise UploadRejected('not_a_file_question', _('This question does not accept files.'))

    content_type = (uploaded_file.content_type or '').lower().split(';')[0].strip()
    if content_type not in allowed:
        raise UploadRejected('type_not_allowed', _('This file type is not accepted here.'))

    max_bytes = effective_max_bytes(question)
    if uploaded_file.size > max_bytes:
        mb = max_bytes // (1024 * 1024)
        raise UploadRejected('too_large', _('The file is too large (limit %(mb)s MB).') % {'mb': mb})

    signatures = _MAGIC.get(content_type)
    if signatures:
        head = uploaded_file.read(16)
        uploaded_file.seek(0)
        if not any(head.startswith(sig) for sig in signatures):
            raise UploadRejected('content_mismatch', _('The file does not match its declared type.'))
        if content_type == 'image/webp' and head[8:12] != b'WEBP':
            raise UploadRejected('content_mismatch', _('The file does not match its declared type.'))

    return content_type


def check_session_caps(session):
    """Raise UploadRejected when the session has already uploaded its share."""
    from django.db.models import Count, Sum

    stats = session.uploads.aggregate(n=Count('token'), total=Sum('size'))
    if (stats['n'] or 0) >= SESSION_MAX_FILES:
        raise UploadRejected('session_file_cap', _('Too many files in this response.'))
    if (stats['total'] or 0) >= SESSION_MAX_BYTES:
        raise UploadRejected('session_byte_cap', _('The files in this response are too large overall.'))


def attach_upload(session, question, token):
    """Resolve a posted token to this session's Upload for this question.

    Returns the Upload marked attached, or None — a foreign, mistyped or
    absent token skips the answer rather than failing the section: the
    respondent's other answers are worth more than a broken reference.
    """
    from survey.models import Upload

    try:
        upload = Upload.objects.get(token=token, session=session, question=question)
    except (Upload.DoesNotExist, ValueError, TypeError):
        return None
    if not upload.attached:
        upload.attached = True
        upload.save(update_fields=['attached'])
    return upload


def detach_unreferenced(session, question_ids):
    """After a section rewrite, uploads no Answer points at anymore go back to
    attached=False so orphan reclamation can collect a replaced file."""
    from survey.models import Upload

    (Upload.objects
        .filter(session=session, question_id__in=question_ids, attached=True)
        .filter(answer__isnull=True)
        .update(attached=False))


# How many files one question accepts. Photo defaults to several — "add photos
# of the place" is the natural ask; audio and documents default to one. The
# creator can set 1..PLATFORM_MAX_FILES per question.
PLATFORM_MAX_FILES = 10
DEFAULT_MAX_FILES = {'photo': 5, 'audio': 1, 'document': 3}


def max_files_for(question):
    vs = question.validation_settings or {}
    value = vs.get('max_files')
    if isinstance(value, (int, float)) and value >= 1:
        return min(int(value), PLATFORM_MAX_FILES)
    return DEFAULT_MAX_FILES.get(question.input_type, 1)
