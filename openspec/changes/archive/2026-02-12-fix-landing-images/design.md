## Approach

Use Django's built-in `django.conf.urls.static.static()` helper to append media serving routes when `DEBUG=True`. This is the standard Django pattern for development media serving.

## Detail

In `mapsurvey/urls.py`:
1. Add `from django.conf import settings` and `from django.conf.urls.static import static`
2. Append `static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)` to `urlpatterns`
3. Remove unused `from django.views.static import serve` import

No changes needed in settings, models, or templates — the `MEDIA_URL` and `MEDIA_ROOT` are already correctly configured.

## Risks

None. This is a standard Django pattern. Only active when `DEBUG=True`; production uses S3.
