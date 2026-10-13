"""Distinct ids for server-side PostHog events sent on behalf of anonymous visitors.

Shared by the marketing-page forms (`/pro/`, `/demo/`) so both stitch a
submission onto the same person as the visitor's `$pageview`s whenever they can.
"""
import json


def anonymous_distinct_id(request, fallback):
    """A distinct id for an anonymous submitter. Never None.

    Preference order matters. The browser snippet keeps its device id in a
    `ph_<key>_posthog` cookie, so reusing it makes a server-side event land on the
    same person as their `$pageview`s -- the difference between "someone
    submitted" and "the visitor who read the whole page submitted". The session
    key is second best: it groups one visitor's events without tying them to
    the pageview stream.

    `fallback` (an id the caller builds from the stored row) exists because the
    first two are routinely absent: an ad blocker stops the snippet from ever writing a cookie, and Django has no
    session key until something writes to the session. Returning None there
    would silently drop the event for exactly the anonymous majority the page
    is built to hear from -- so every stored answer gets counted, even when it
    cannot be stitched to a person.
    """
    for name, value in request.COOKIES.items():
        if not (name.startswith('ph_') and name.endswith('_posthog')):
            continue
        try:
            distinct_id = json.loads(value).get('distinct_id')
        except (ValueError, AttributeError):
            continue
        if distinct_id:
            return str(distinct_id)
    if request.session.session_key:
        return f"anon_session_{request.session.session_key}"
    return fallback
