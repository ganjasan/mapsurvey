"""The operator entry form (change operator-entry, #355; spec operator-entry).

A workspace member (editor role and up, Pro feature `operator_entry`) enters a
survey's answers on someone's behalf: a paper sheet after an event, an assisted
interview, a field observation. The result is an ordinary `SurveySession` with
`source` != `online` and `entered_by` set, stored by the SAME section writer the
respondent page uses (`views.save_section_answers`), judged for the `operator`
surface (spec question-audience).

Differences from the respondent page, and why each one exists:

* The session rides the URL, never the respondent cookie `survey_session_id`, so
  an operator who also answers on the public link stays a respondent there.
* No `SurveyEvent`, no shared-map materialisation, no demo open, no PostHog
  (`POSTHOG_EXCLUDED_VIEW_NAMES`): these sessions are answers, not respondents.
* `check_survey_access` is not on this path: a closed survey is exactly where
  sheets get entered; the editor role is the gate.
* Respondent-facing `required` is soft (a blank on paper is a blank); an
  operator-only question keeps its own.
"""
from urllib.parse import urlencode

from django import forms
from django.http import Http404, HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import translation
from django.utils.translation import gettext_lazy as _

from billing.gates import require_feature

from .models import SurveyHeader, SurveySection, SurveySession
from .permissions import survey_permission_required
from .question_types import SURFACE_OPERATOR
from .versioning import canonical_of, family_headers, family_ids

OPERATOR_SOURCE_CHOICES = [
    (value, label) for value, label in SurveySession.SOURCE_CHOICES
    if value in SurveySession.OPERATOR_SOURCES
]


def _survey_org(request, *args, **kwargs):
    return request.survey.organization


def entry_gate(view):
    """Editor role on the survey, then the Pro feature on its organisation —
    checked on every request, so a lapsed subscription stops new entries."""
    return survey_permission_required('editor')(
        require_feature('operator_entry', _survey_org)(view))


def _version_label(header, canonical):
    if header.pk == canonical.pk:
        return _('v%(n)s — current') % {'n': header.version_number}
    return _('v%(n)s — archived') % {'n': header.version_number}


class EntryHeaderForm(forms.Form):
    """What a respondent never chooses: where the answers came from, which
    version of the survey the sheet was printed from, and its language."""
    source = forms.ChoiceField(
        label=_('Where do these answers come from?'),
        choices=OPERATOR_SOURCE_CHOICES, widget=forms.RadioSelect)
    version = forms.TypedChoiceField(label=_('Survey version'), coerce=int)
    language = forms.ChoiceField(label=_('Language of the answers'), required=False)

    def __init__(self, *args, survey, **kwargs):
        super().__init__(*args, **kwargs)
        canonical = canonical_of(survey)
        self.headers = {h.pk: h for h in family_headers(canonical)}
        self.fields['version'].choices = [
            (h.pk, _version_label(h, canonical)) for h in self.headers.values()]
        self.fields['version'].initial = canonical.pk
        languages = list(canonical.available_languages or [])
        if languages:
            from .templatetags.survey_filters import language_name
            self.fields['language'].choices = [(code, language_name(code)) for code in languages]
            self.fields['language'].initial = languages[0]
            self.fields['language'].required = True
        else:
            self.fields['language'].widget = forms.HiddenInput()
            self.fields['language'].choices = [('', '')]
        self.show_version = len(self.headers) > 1
        self.show_language = len(languages) > 1

    def chosen_header(self):
        return self.headers[self.cleaned_data['version']]


def _head_section(header):
    return SurveySection.objects.filter(survey_header=header, is_head=True).first()


def _entry_session(request, session_id):
    """The session behind an entry URL: of this survey's family, entered by an
    operator (never a respondent's), not trashed. Anything else is a 404."""
    survey = request.survey
    session = SurveySession.objects.select_related('survey').filter(
        pk=session_id, survey_id__in=family_ids(survey), is_deleted=False,
    ).exclude(source=SurveySession.SOURCE_ONLINE).first()
    if session is None:
        raise Http404
    return session


def _vmap(session):
    from .visibility import answers_by_code_for_session, compute_visibility
    return compute_visibility(session.survey, answers_by_code_for_session(session),
                              surface=SURFACE_OPERATOR)


def _section_url(survey, session, section):
    return reverse('operator_entry_section', args=[survey.uuid, session.pk, section.name])


def _saved_url(survey, session):
    return reverse('operator_entry_saved', args=[survey.uuid, session.pk])


def first_section_url(survey, session, unanswered_first=False):
    """Where an entry starts: the first visible section — or, for a sheet opened
    again (change paper-photo-entry), the first one without a stored answer."""
    from .models import Answer
    vmap = _vmap(session)
    chain = vmap.visible_sections
    if not chain:
        return _saved_url(survey, session)
    if unanswered_first:
        answered = set(Answer.objects.filter(
            survey_session=session, parent_answer_id__isnull=True,
        ).values_list('question__survey_section_id', flat=True))
        for section in chain:
            if section.id not in answered:
                return _section_url(survey, session, section)
    return _section_url(survey, session, chain[0])


def _sheet_context(survey, session, section, questions):
    """Prefill, doubtful/blank codes and the page pane for a sheet session
    (change paper-photo-entry); empty for a typed-in session."""
    sheet = session.paper_sheet
    if sheet is None:
        return {}, {}
    from .paper.review import page_for_section, sheet_prefill
    initial, doubtful, blank = sheet_prefill(sheet, questions)
    page, pages = page_for_section(sheet, section)
    batch_url = reverse('paper_batch', args=[survey.uuid, sheet.batch_id])
    pane = {
        'paper_sheet': sheet,
        'paper_page': page,
        'paper_pages': [{
            'id': p.pk, 'number': p.page_number,
            'url': reverse('paper_page_image', args=[survey.uuid, sheet.batch_id, p.pk]),
        } for p in pages],
        'paper_doubtful': doubtful,
        'paper_blank': blank,
        'paper_review': True,
        'entry_cancel_url': batch_url,
    }
    return initial, pane


@entry_gate
def entry_header(request, survey_uuid):
    """Step 1: source, version, language. POST creates the session."""
    from .views import session_kind_for
    survey = request.survey
    if request.method == 'POST':
        form = EntryHeaderForm(request.POST, survey=survey)
        if form.is_valid():
            header = form.chosen_header()
            session = SurveySession.objects.create(
                survey=header,
                language=form.cleaned_data.get('language') or None,
                source=form.cleaned_data['source'],
                entered_by=request.user,
                opened_by_kind=session_kind_for(request, header),
            )
            vmap = _vmap(session)
            if not vmap.visible_sections:
                return redirect(_saved_url(survey, session))
            return redirect(_section_url(survey, session, vmap.visible_sections[0]))
    else:
        # "Next sheet" carries the previous header in the query string.
        initial = {k: request.GET[k] for k in ('source', 'version', 'language') if request.GET.get(k)}
        form = EntryHeaderForm(initial=initial, survey=survey)
    return render(request, 'editor/operator_entry/header.html', {
        'survey': survey, 'form': form,
    })


@entry_gate
def entry_section(request, survey_uuid, session_id, section_name):
    """Step 2..n: one section of the survey in entry mode, posted to itself."""
    from .views import _add_shell_context, _build_section_context, save_section_answers
    survey = request.survey
    session = _entry_session(request, session_id)
    session_survey = session.survey
    section = SurveySection.objects.filter(survey_header=session_survey, name=section_name).first()
    if section is None:
        raise Http404
    if session.language:
        translation.activate(session.language)

    vmap = _vmap(session)
    if request.method == 'POST':
        vmap = save_section_answers(request.POST, session, session_survey, section,
                                    surface=SURFACE_OPERATOR)
        chain = vmap.visible_sections
        ids = [s.id for s in chain]
        pos = ids.index(section.id) if section.id in ids else 0
        back = request.POST.get('nav_direction') == 'back'
        target = (chain[pos - 1] if back and pos > 0 else
                  chain[pos + 1] if not back and pos + 1 < len(chain) else None)
        url = _section_url(survey, session, target) if target else _saved_url(survey, session)
        if request.headers.get('HX-Request') == 'true':
            response = HttpResponse()
            response['HX-Redirect'] = url
            return response
        return HttpResponseRedirect(url)

    chain_ids = [s.id for s in vmap.visible_sections]
    if section.id not in chain_ids:
        # Hidden for this sheet's answers (or for operators): start of the chain.
        if not chain_ids:
            return redirect(_saved_url(survey, session))
        return redirect(_section_url(survey, session, vmap.visible_sections[0]))
    current, total = chain_ids.index(section.id) + 1, len(chain_ids)
    prefill, pane = _sheet_context(survey, session, section, list(section.questions()))
    ctx = _build_section_context(request, survey, session_survey, section, session.language,
                                 current, total, vmap=vmap, session_id=session.pk, entry=True,
                                 prefill=prefill or None)
    ctx.update({
        'form_post_url': _section_url(survey, session, section),
        'entry_session': session,
        'entry_cancel_url': reverse('editor_survey_analytics', args=[survey.uuid]),
        'is_last_section': current == total,
    })
    ctx.update(pane)
    _add_shell_context(ctx, session_survey, section)
    return render(request, 'editor/operator_entry/section.html', ctx)


@entry_gate
def entry_saved(request, survey_uuid, session_id):
    """The sheet is stored: mark it completed and offer the next one."""
    survey = request.survey
    session = _entry_session(request, session_id)
    session.mark_completed()
    ctx = {
        'survey': survey,
        'session': session,
        'responses_url': reverse('editor_survey_analytics', args=[survey.uuid]),
    }
    sheet = session.paper_sheet
    if sheet is not None:
        # A sheet reviewed from photos (change paper-photo-entry): mark it entered, drop
        # its images, and offer the batch's next sheet instead of the header.
        _finish_sheet(request, sheet, session)
        from .paper.sheets import next_reviewable
        following = next_reviewable(sheet.batch, after=sheet) or next_reviewable(sheet.batch)
        ctx.update({
            'paper_sheet': sheet,
            'batch_url': reverse('paper_batch', args=[survey.uuid, sheet.batch_id]),
            'next_sheet_url': (reverse('paper_sheet_enter', args=[survey.uuid, sheet.batch_id, following.pk])
                               if following else ''),
        })
    else:
        next_query = urlencode({
            'source': session.source,
            'version': session.survey_id,
            'language': session.language or '',
        })
        ctx['next_url'] = reverse('operator_entry_header', args=[survey.uuid]) + '?' + next_query
    return render(request, 'editor/operator_entry/saved.html', ctx)


def _finish_sheet(request, sheet, session):
    """Idempotent: a reload of the Saved page must not count the sheet twice."""
    from django.utils import timezone
    from . import product_events as pe
    from .paper.review import changed_fields
    from .tasks import delete_sheet_images
    if sheet.status == 'entered':
        return
    sheet.status = 'entered'
    sheet.entered_at = timezone.now()
    sheet.save(update_fields=['status', 'entered_at'])
    total, doubtful, changed = changed_fields(sheet, session)
    pe.emit(pe.PAPER_SHEET_ENTERED, request.user.pk, {
        'survey_id': request.survey.pk,
        'fields_total': total, 'fields_doubtful': doubtful, 'fields_changed': changed,
    })
    delete_sheet_images.delay(sheet.pk)
    sheet.batch.touch()
