"""Template helpers for sites (change landing-documents-map)."""
from django import template

from survey.sites import TYPE_LABELS

register = template.Library()


@register.filter
def document_type(extension):
    return TYPE_LABELS.get((extension or '').lower(), (extension or '').upper())
