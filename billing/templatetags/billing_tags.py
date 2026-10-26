from django import template

from ..entitlements import for_organization
from ..features import FEATURES, PLAN_LABELS

register = template.Library()


@register.simple_tag
def has_feature(organization, feature_key):
    """`{% has_feature survey.organization "unbranded" as unbranded %}`"""
    if organization is None:
        return False
    return for_organization(organization).has(feature_key)


@register.simple_tag
def entitlements_for(organization):
    return for_organization(organization)


@register.simple_tag
def ppg_products_configured():
    """True when PayPro products are configured -- the switch for every Upgrade control."""
    from ..checkout import products_configured
    return products_configured()


@register.simple_tag
def plan_label(plan_code):
    return PLAN_LABELS.get(plan_code, plan_code)


@register.simple_tag
def plan_feature_labels(plan_code):
    """Labels of every feature a plan unlocks, in registry order -- the plan cards' bullets."""
    return [f.label for f in FEATURES.values() if plan_code in f.plans]


@register.simple_tag
def feature_label(feature_key):
    f = FEATURES.get(feature_key)
    return f.label if f else feature_key
