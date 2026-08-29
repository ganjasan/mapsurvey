import json
from django import template
from django.utils.translation import gettext as _
from django.utils.safestring import mark_safe

register = template.Library()


@register.simple_tag
def i18n_json():
    """
    Returns a JSON object with translated strings for JavaScript.
    Usage: <body data-i18n='{% i18n_json %}'>
    """
    translations = {
        # Draw button labels
        'startDrawing': _('Start drawing'),
        'finishDrawing': _('Finish drawing'),
        'finishEditing': _('Finish editing'),
        'cancel': _('Cancel'),
        'delete': _('Delete'),

        # Marker tooltips
        'clickToPlaceMarker': _('Click on the map to place a marker.'),

        # Polygon tooltips
        'clickToStartShape': _('Click to start drawing a shape.'),
        'clickToContinueShape': _('Click to continue drawing the shape.'),
        'clickFirstPointToClose': _('Click the first point to close this shape.'),

        # Polyline tooltips
        'clickToStartLine': _('Click to start drawing a line.'),
        'clickToContinueLine': _('Click to continue drawing the line.'),
        'clickLastPointToFinish': _('Click the last point to finish the line.'),

        # Touch variants: on coarse pointers "click" instructions describe an
        # interaction that does not exist (audit finding — the map ignores taps
        # until a tool is active). The template picks these via pointer:coarse.
        'tapToPlaceMarker': _('Move the map to position the pin, then press Apply.'),
        'tapToStartShape': _('Tap to add the shape’s corners.'),
        'tapToContinueShape': _('Tap to add the next corner.'),
        'tapFirstPointToClose': _('Tap the first point to close the shape.'),
        'tapToStartLine': _('Tap to start the line.'),
        'tapToContinueLine': _('Tap to add the next point.'),
        'tapLastPointToFinish': _('Tap the last point to finish the line.'),


        # Error messages
        'shapeEdgesCannotIntersect': _('<strong>Error:</strong> Shape edges cannot intersect!'),

        # Geocoding search
        'searchAddress': _('Search address...'),
        'noResultsFound': _('No results found'),
        'searchFailed': _('Search failed — check your connection and try again.'),

        # Multi-feature geo questions
        'addAnother': _('Add another'),
        'upToNMore': _('up to {n} more'),
        'maximumReachedHint': _('Maximum reached — remove one below to change it.'),
        'nMarked': _('{n} marked'),
        'nOfMMarked': _('{n} of {m} marked'),
        'atLeastNRequired': _('at least {n} required'),
        'allMarkedThanks': _('All {m} marked — thank you!'),
    }
    return mark_safe(json.dumps(translations, ensure_ascii=False))


@register.simple_tag
def creator_languages():
    """settings.LANGUAGES with the names left exactly as configured.

    Django's own {% get_available_languages %} does NOT hand back the setting
    untouched — it runs each name through gettext:

        [(k, translation.gettext(v)) for k, v in settings.LANGUAGES]

    Django ships translations for language names, so "English" became "Anglais"
    for a French creator and "Englisch" for a German one. "Deutsch" and
    "Français" survived only because Django names those languages in English
    ("German", "French") and has no msgid matching ours — the correct entries
    were protected by accident.

    Every name must read in its own language: the person who needs the switcher
    is the one who cannot read the current interface.
    """
    from django.conf import settings as dj_settings
    return list(dj_settings.LANGUAGES)
