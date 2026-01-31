from django.conf import settings


def mapbox(request):
    return {
        'MAPBOX_URL': settings.MAPBOX_URL,
        'MAPBOX_ACCESS_TOKEN': settings.MAPBOX_ACCESS_TOKEN,
    }
