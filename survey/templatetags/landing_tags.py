"""Template helpers for landing pages (change landing-documents-map)."""
from django import template

from survey.landings import TYPE_LABELS

register = template.Library()


@register.filter
def document_type(extension):
    return TYPE_LABELS.get((extension or '').lower(), (extension or '').upper())
