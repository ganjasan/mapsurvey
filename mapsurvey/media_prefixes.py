"""Key prefixes for the media bucket.

Deliberately free of Django imports: `settings.py` calls this at module level,
long before the app registry exists, so anything importing `django.conf` here
would blow up at startup.
"""


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
    """
    explicit = env.get('MEDIA_S3_NAMESPACE')
    if explicit is not None:
        return explicit.strip('/')

    if env.get('IS_PULL_REQUEST') == 'true':
        # Never fall through to production's prefix on a preview: an unnamed
        # preview writing into `media/` would put test files in front of real
        # respondents, and could overwrite a creator's cover image.
        service = (env.get('RENDER_SERVICE_NAME') or '').strip('/')
        return f'previews/{service}' if service else 'previews/unnamed'

    return ''
