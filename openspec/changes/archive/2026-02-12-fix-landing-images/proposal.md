## Why

Images on the landing page (Story cover images) return 404 because Django has no URL route to serve media files. The `serve` view is imported in `urls.py` but never wired up, so requests to `/mediafiles/stories/*` fall through to a 404.

## What Changes

- Add media file serving URL pattern in `mapsurvey/urls.py` using `django.conf.urls.static.static()` helper for development (`DEBUG=True`)
- Remove unused `from django.views.static import serve` import (replaced by the `static()` helper)

## Capabilities

### New Capabilities

_(none)_

### Modified Capabilities

_(none — this is a bug fix in URL wiring, no spec-level behavior changes)_

## Impact

- **URLs**: `mapsurvey/urls.py` — add `static(MEDIA_URL, document_root=MEDIA_ROOT)` to urlpatterns
- **Scope**: Development only (`DEBUG=True`); production uses S3 via `USE_S3` setting
- **Risk**: None — standard Django pattern for dev media serving
