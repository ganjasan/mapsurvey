"""The form download (spec printable-form, requirement "A form is printed from the
Share page for any status")."""
from django.http import HttpResponse, HttpResponseBadRequest
from django.utils.http import content_disposition_header
from django.utils.text import slugify

from survey import product_events as pe
from survey.embedding import public_base_url
from survey.models import PrintedForm, PrintRun
from survey.permissions import survey_permission_required
from survey.print.pdf import build_form, print_copies

PAPER_CHOICES = tuple(code for code, _label in PrintedForm.PAPER_CHOICES)


def default_paper(request):
    """US Letter for a creator whose interface locale is en-US / en-CA, else A4."""
    from django.utils import translation
    locale = (translation.get_language_from_request(request) or '').lower()
    header = (request.META.get('HTTP_ACCEPT_LANGUAGE', '') or '').lower()
    if locale in ('en-us', 'en-ca') or header.startswith(('en-us', 'en-ca')):
        return PrintedForm.PAPER_LETTER
    return PrintedForm.PAPER_A4


@survey_permission_required('editor')
def print_form(request, survey_uuid):
    """`?mode=copies&copies=N` prints N numbered copies (change paper-photo-entry):
    each continues the survey's copy numbering, so photos of them sort themselves.
    Without `mode` (or `mode=single`) one copy without numbers, to photocopy."""
    survey = request.survey
    languages = list(survey.available_languages or ['en'])
    language = request.GET.get('lang') or languages[0]
    paper = request.GET.get('paper') or PrintedForm.PAPER_A4
    mode = request.GET.get('mode') or 'single'
    if language not in languages:
        return HttpResponseBadRequest('unknown language')
    if paper not in PAPER_CHOICES:
        return HttpResponseBadRequest('unknown paper')
    if mode not in ('single', 'copies'):
        return HttpResponseBadRequest('unknown mode')
    slug = slugify(survey.name) or 'survey'
    keep = request.GET.get('keep') == '1'   # keep each map with its tables on one page
    if mode == 'copies':
        try:
            copies = int(request.GET.get('copies') or 0)
        except ValueError:
            copies = 0
        if not 1 <= copies <= PrintRun.MAX_COPIES:
            return HttpResponseBadRequest(f'copies must be 1..{PrintRun.MAX_COPIES}')
        result = print_copies(survey, language, paper, copies, user=request.user, base_url=public_base_url(request),
                              keep=keep)
        # result.run: the PrintRun these copies were numbered from
        filename = f'{slug}-form-{language}-{paper}-copies-{result.run.first_copy}-{result.run.last_copy}.pdf'
        props = {'copies': result.run.count}
    else:
        result = build_form(survey, language, paper, user=request.user, base_url=public_base_url(request), keep=keep)
        filename = f'{slug}-form-{language}-{paper}.pdf'
        props = {'copies': 0}
    pe.emit(pe.FORM_PRINTED, request.user.pk, {
        'survey_id': str(survey.id), 'paper': paper, 'language': language,
        'pages': result.pages, 'map_pages': result.map_pages, 'keep_together': keep, **props,
    })
    response = HttpResponse(result.pdf, content_type='application/pdf')
    response['Content-Disposition'] = content_disposition_header(True, filename)
    response['X-Form-Code'] = result.form.code
    return response
