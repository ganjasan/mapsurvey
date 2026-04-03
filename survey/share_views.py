from django import forms
from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST

from .models import TrackedLink
from .permissions import survey_permission_required


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

    links = TrackedLink.objects.filter(survey=survey)
    link_data = [
        {'obj': link, 'url': link.build_url(request)}
        for link in links
    ]

    return render(request, 'editor/survey_share.html', {
        'survey': survey,
        'form': form,
        'links': link_data,
        'effective_role': request.effective_survey_role,
    })


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
