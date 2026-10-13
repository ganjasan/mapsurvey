from django import forms
from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST

from django.utils.translation import gettext_lazy as _

from .embedding import normalise_allowed_hosts, snippet_html, public_base_url, InvalidHost
from .models import TrackedLink, PublicResultsPage
from .permissions import survey_permission_required
from .versioning import canonical_of


class EmbedHostsForm(forms.Form):
    """The Share page's allowed-hosts box (change embed-surveys).

    One host per line; the clean step does the tidying a creator would do by
    hand (drop the pasted scheme and path, lower-case) and names the first
    entry it cannot read.
    """
    allowed_hosts = forms.CharField(
        required=False,
        label=_('Sites allowed to embed'),
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'city.example.org\n*.consult.example',
            'style': 'font-family:monospace;font-size:0.85rem;',
        }),
    )

    def clean_allowed_hosts(self):
        try:
            return normalise_allowed_hosts(self.cleaned_data['allowed_hosts'])
        except InvalidHost as exc:
            raise forms.ValidationError(
                _('"%(host)s" is not a host name. Use just the domain, like city.example.org or *.example.org.'),
                params={'host': str(exc)},
            )


class TrackedLinkForm(forms.ModelForm):
    class Meta:
        model = TrackedLink
        fields = ['utm_source', 'utm_medium', 'utm_campaign']
        widgets = {
            'utm_source': forms.TextInput(attrs={
                'placeholder': 'e.g. newsletter, instagram, poster',
                'class': 'form-control',
            }),
            'utm_medium': forms.TextInput(attrs={
                'placeholder': 'e.g. email, social, print',
                'class': 'form-control',
            }),
            'utm_campaign': forms.TextInput(attrs={
                'placeholder': 'e.g. spring2026, launch',
                'class': 'form-control',
            }),
        }
        labels = {
            'utm_source': 'Source',
            'utm_medium': 'Medium',
            'utm_campaign': 'Campaign',
        }


def _render_share(request, survey, form=None, embed_form=None, status=200):
    """The Share page, for both its forms (tracked links, embed hosts)."""
    links = TrackedLink.objects.filter(survey=survey)
    link_data = [{'obj': link, 'url': link.build_url(request)} for link in links]

    # A shared link only reaches the public when the survey is published; every other
    # status 404s (or is test-token only), so gate the copyable links behind that and
    # nudge the creator to publish first (see backlog: publish-prompt-on-share-draft).
    is_shareable = survey.status == 'published'
    can_publish, publish_blocked_reason = survey.can_transition_to('published')

    # The results page (auto-drafted at publish time) and the embed allow-list live on
    # the canonical row -- that is what respondents reach, whichever version this page
    # was opened on (change embed-surveys).
    canonical = canonical_of(survey)
    results_page = PublicResultsPage.objects.filter(survey=canonical).first()
    if embed_form is None:
        embed_form = EmbedHostsForm(initial={'allowed_hosts': '\n'.join(canonical.embed_allowed_hosts or [])})

    return render(request, 'editor/survey_share.html', {
        'survey': survey,
        'public_base': public_base_url(request),
        'form': form or TrackedLinkForm(),
        'links': link_data,
        'effective_role': request.effective_survey_role,
        'is_shareable': is_shareable,
        'can_publish': can_publish,
        'publish_blocked_reason': publish_blocked_reason,
        'results_page': results_page,
        'embed_snippet': snippet_html(request, canonical) if is_shareable else '',
        'embed_form': embed_form,
        'embed_hosts_saved': status == 200 and request.GET.get('embed') == 'saved',
    }, status=status)


@survey_permission_required('editor')
def share_page(request, survey_uuid):
    """Share page: create and manage tracked links with UTM params."""
    survey = request.survey

    if request.method == 'POST':
        form = TrackedLinkForm(request.POST)
        if form.is_valid():
            link = form.save(commit=False)
            link.survey = survey
            link.save()
            return redirect('editor_survey_share', survey_uuid=survey_uuid)
    else:
        form = TrackedLinkForm()

    return _render_share(request, survey, form=form)


@survey_permission_required('editor')
@require_POST
def embed_settings(request, survey_uuid):
    """Save the allowed-hosts list from the Share page's Embed section (change embed-surveys)."""
    survey = request.survey
    embed_form = EmbedHostsForm(request.POST)
    if not embed_form.is_valid():
        return _render_share(request, survey, embed_form=embed_form, status=400)
    canonical = canonical_of(survey)
    canonical.embed_allowed_hosts = embed_form.cleaned_data['allowed_hosts']
    canonical.save(update_fields=['embed_allowed_hosts', 'updated_at'])
    from django.urls import reverse
    return redirect(reverse('editor_survey_share', kwargs={'survey_uuid': survey_uuid}) + '?embed=saved#embed')


@survey_permission_required('editor')
@require_POST
def share_link_delete(request, survey_uuid, link_id):
    """Delete a tracked link."""
    survey = request.survey
    link = get_object_or_404(TrackedLink, id=link_id, survey=survey)
    link.delete()
    if request.headers.get('HX-Request'):
        return HttpResponse('')
    return redirect('editor_survey_share', survey_uuid=survey_uuid)
