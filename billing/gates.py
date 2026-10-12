"""Gate helpers: the view decorator and the template tag's backing function.

Both consult `entitlements.for_organization` and nothing else, so a feature
is granted or refused by one rule wherever it is checked.
"""
from functools import wraps

from django.http import HttpResponseForbidden
from django.shortcuts import render

from .entitlements import for_organization


def require_feature(feature_key, org_getter):
    """Refuse (403, with an upgrade hint) unless the organisation holds the feature.

    `org_getter(request, *args, **kwargs)` returns the organisation the view is
    about; existence and membership checks stay in the view/decorators that
    already do them -- this only decides Pro vs not."""
    def deco(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            org = org_getter(request, *args, **kwargs)
            ent = for_organization(org)
            if not ent.has(feature_key):
                return render(request, 'billing/feature_required.html',
                              {'org': org, 'feature_key': feature_key, 'entitlements': ent}, status=403)
            return view(request, *args, **kwargs)
        return wrapper
    return deco
