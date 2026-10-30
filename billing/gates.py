"""Gate helpers: the view decorator and the template tag's backing function.

Both consult `entitlements.for_organization` and nothing else, so a feature
is granted or refused by one rule wherever it is checked.
"""
from functools import wraps

from django.http import HttpResponseForbidden
from django.shortcuts import render

from .entitlements import for_organization


def feature_required(request, org, feature_key, status=403):
    """The refusal page: what the feature is, and where the viewer's Pro trial stands."""
    from survey.permissions import get_org_membership

    from .trial import state_for
    m = get_org_membership(request.user, org) if request.user.is_authenticated else None
    trial = state_for(org, request.user)
    return render(request, 'billing/feature_required.html', {
        'org': org, 'feature_key': feature_key, 'entitlements': for_organization(org),
        'trial': trial, 'feature_used_up': trial.feature_exhausted(feature_key),
        'is_owner': m is not None and m.role == 'owner',
        'next_path': request.get_full_path() if request.method == 'GET' else '',
    }, status=status)


def require_feature(feature_key, org_getter):
    """Refuse (403, with an upgrade hint) unless the organisation may use the feature
    (its plan includes it, a live Pro trial has a remainder for it, or the use
    would start the trial -- `billing.trial.may`).

    `org_getter(request, *args, **kwargs)` returns the organisation the view is
    about; existence and membership checks stay in the view/decorators that
    already do them -- this only decides Pro vs not. It starts and counts
    nothing: that is the view's `billing.trial.use`, at the point the feature
    is actually used."""
    from . import trial

    def deco(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            org = org_getter(request, *args, **kwargs)
            if not trial.may(org, feature_key):
                return feature_required(request, org, feature_key)
            return view(request, *args, **kwargs)
        return wrapper
    return deco
