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
from functools import wraps
from urllib.parse import urlencode

from django import forms
from django.http import Http404, HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import translation
from django.utils.translation import gettext_lazy as _

from billing import trial as billing_trial
from billing.entitlements import for_organization
from billing.gates import feature_required, require_feature

from .audit import audit
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
    checked on every request, so a lapsed subscription stops new entries. A
    workspace whose first sheet would start its Pro trial is admitted too
    (change pro-trial-auto); the header POST starts and counts it."""
    return survey_permission_required('editor')(
        require_feature('operator_entry', _survey_org)(view))


def sheet_gate(view):
    """For the pages of a sheet already created: editor role, and the feature
    still in force (`covers`) — a trial allowance spent by this very sheet must
    not strand it half-entered. Nothing is counted here."""
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        org = request.survey.organization
        if not for_organization(org).covers('operator_entry'):
            return feature_required(request, org, 'operator_entry')
        return view(request, *args, **kwargs)
    return survey_permission_required('editor')(wrapper)


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


#: Where an entry opened from Responses goes back to (change
#: operator-edit-from-responses, #527): the response in the drawer, or that and
#: its full-size map. Any other value is ignored.
RETURN_TARGETS = ('response', 'map')


def _return_to(request):
    value = request.GET.get('return_to', '')
    return value if value in RETURN_TARGETS else None


def _section_url(survey, session, section, return_to=None):
    url = reverse('operator_entry_section', args=[survey.uuid, session.pk, section.name])
    return url + '?' + urlencode({'return_to': return_to}) if return_to else url


def _response_url(survey, session, return_to):
    """Responses with this session open in the drawer (and its map for `map`)."""
    query = {'session': session.pk}
    if return_to == 'map':
        query['map'] = 1
    return reverse('editor_survey_analytics', args=[survey.uuid]) + '?' + urlencode(query)


def edit_links(request, survey, session):
    """The entry-form links the Responses drawer offers for one session, or None.

    Only an operator session that is not trashed, only for the editor role and
    up, and only while the organisation is covered for `operator_entry` — the
    same test `sheet_gate` applies, so a link never leads to a refusal. Returns
    `start` (the first visible section) and `section(name, return_to)`."""
    if (request.effective_survey_role not in ('editor', 'owner')
            or not session.is_operator_entry or session.is_deleted
            or not for_organization(survey.organization).covers('operator_entry')):
        return None
    chain = _vmap(session).visible_sections

    def section(name, return_to='response'):
        url = reverse('operator_entry_section', args=[survey.uuid, session.pk, name])
        return url + '?' + urlencode({'return_to': return_to})

    return {
        'start': section(chain[0].name) if chain else None,
        'section': section,
    }


def _saved_url(survey, session):
    return reverse('operator_entry_saved', args=[survey.uuid, session.pk])


@entry_gate
def entry_header(request, survey_uuid):
    """Step 1: source, version, language. POST creates the session."""
    from .views import session_kind_for
    survey = request.survey
    if request.method == 'POST':
        form = EntryHeaderForm(request.POST, survey=survey)
        if form.is_valid():
            header = form.chosen_header()
            # One sheet is one use of `operator_entry`; the first one of a
            # workspace that never had a trial starts it (change pro-trial-auto).
            org = survey.organization
            if not billing_trial.use(org, 'operator_entry', actor=request.user):
                return feature_required(request, org, 'operator_entry')
            billing_trial.flash_started(request, org)
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


@sheet_gate
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

    return_to = _return_to(request)
    vmap = _vmap(session)
    if request.method == 'POST':
        # A save on a sheet that was already finished changes it (change
        # operator-edit-from-responses): ids only, never the answers.
        finished = session.end_datetime is not None
        vmap = save_section_answers(request.POST, session, session_survey, section,
                                    surface=SURFACE_OPERATOR)
        if finished:
            audit(request, 'response_edit', survey, session_id=session.pk, section=section.code)
        direction = request.POST.get('nav_direction')
        chain = vmap.visible_sections
        ids = [s.id for s in chain]
        pos = ids.index(section.id) if section.id in ids else 0
        back = direction == 'back'
        target = (chain[pos - 1] if back and pos > 0 else
                  chain[pos + 1] if not back and pos + 1 < len(chain) else None)
        if direction == 'return' and return_to:
            # One section fixed: back to the response, the sheet's completion untouched.
            url = _response_url(survey, session, return_to)
        elif target:
            url = _section_url(survey, session, target, return_to)
        else:
            url = _saved_url(survey, session)
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
        return redirect(_section_url(survey, session, vmap.visible_sections[0], return_to))
    current, total = chain_ids.index(section.id) + 1, len(chain_ids)
    ctx = _build_section_context(request, survey, session_survey, section, session.language,
                                 current, total, vmap=vmap, session_id=session.pk, entry=True)
    ctx.update({
        'form_post_url': _section_url(survey, session, section, return_to),
        'entry_session': session,
        'entry_return_to': return_to,
        'entry_cancel_url': (_response_url(survey, session, return_to) if return_to
                             else reverse('editor_survey_analytics', args=[survey.uuid])),
        'is_last_section': current == total,
    })
    _add_shell_context(ctx, session_survey, section)
    return render(request, 'editor/operator_entry/section.html', ctx)


@sheet_gate
def entry_saved(request, survey_uuid, session_id):
    """The sheet is stored: mark it completed and offer the next one."""
    survey = request.survey
    session = _entry_session(request, session_id)
    session.mark_completed()
    next_query = urlencode({
        'source': session.source,
        'version': session.survey_id,
        'language': session.language or '',
    })
    return render(request, 'editor/operator_entry/saved.html', {
        'survey': survey,
        'session': session,
        'next_url': reverse('operator_entry_header', args=[survey.uuid]) + '?' + next_query,
        'responses_url': reverse('editor_survey_analytics', args=[survey.uuid]),
    })
