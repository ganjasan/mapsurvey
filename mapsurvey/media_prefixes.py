"""Key prefixes for the media bucket.

Deliberately free of Django imports: `settings.py` calls this at module level,
long before the app registry exists, so anything importing `django.conf` here
would blow up at startup.
"""


import re
from typing import Optional, Tuple


def media_locations(namespace: Optional[str]) -> Tuple[str, str]:
    """Return the (public, private) key prefixes for one environment.

    Production passes an empty namespace and keeps the bare `media` /`uploads`
    prefixes — that is where the relative paths already stored in the database
    resolve, so moving to S3 rewrites no rows. Every other environment passes
    something like `previews/mapsurvey-pr-123`, which puts its files where they
    cannot collide with production's.
    """
    ns = (namespace or '').strip('/')
    prefix = f'{ns}/' if ns else ''
    return f'{prefix}media', f'{prefix}uploads'


def namespace_from_env(env) -> str:
    """Pick this environment's namespace out of the process environment.

    Render's Blueprint cannot express "name this after the preview service" —
    a preview's name only exists once Render has created it — so the value is
    derived at start-up from the variables Render injects instead.

    An explicit `MEDIA_S3_NAMESPACE` always wins, including when it is set to
    the empty string; that is the escape hatch for pinning an environment
    somewhere specific. Otherwise a pull-request environment gets
    `previews/<service>` and everything else gets production's bare prefixes.

    `MEDIA_NAMESPACE_SERVICE` makes one preview service share another's
    namespace. The Celery worker sets it to `mapsurvey`: its own name is
    `mapsurvey-celery PR #200`, so without it the web service wrote
    `previews/mapsurvey PR #200/…` and the worker looked in
    `previews/mapsurvey-celery PR #200/…` — every file the web hands the worker
    (an import archive, an image-basemap upload) was "missing" on previews.
    Only the service part is replaced; the preview suffix is kept, so the
    namespace is exactly the web preview's name, which is what
    reclaim_preview_media checks against Render's service list.
    """
    explicit = env.get('MEDIA_S3_NAMESPACE')
    if explicit is not None:
        return explicit.strip('/')

    if env.get('IS_PULL_REQUEST') == 'true':
        # Never fall through to production's prefix on a preview: an unnamed
        # preview writing into `media/` would put test files in front of real
        # respondents, and could overwrite a creator's cover image.
        service = (env.get('RENDER_SERVICE_NAME') or '').strip('/')
        owner = (env.get('MEDIA_NAMESPACE_SERVICE') or '').strip('/')
        if service and owner:
            suffix = re.search(r'(\s+PR\s+#\d+|-pr-\d+)$', service, re.IGNORECASE)
            service = owner + (suffix.group(1) if suffix else '')
        return f'previews/{service}' if service else 'previews/unnamed'

    return ''
