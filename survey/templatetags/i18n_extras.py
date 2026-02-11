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
        'finishEditing': _('Finish editing'),
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

        # Error messages
        'shapeEdgesCannotIntersect': _('<strong>Error:</strong> Shape edges cannot intersect!'),

        # Geocoding search
        'searchAddress': _('Search address...'),
        'noResultsFound': _('No results found'),
    }
    return mark_safe(json.dumps(translations, ensure_ascii=False))
