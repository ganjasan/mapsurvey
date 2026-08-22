"""Password rules for the live registration checklist.

The checklist has two kinds of entry and the difference is the whole point:

* **enforced** — derived from `settings.AUTH_PASSWORD_VALIDATORS`. The server
  rejects a password that fails one of these. Deriving them rather than
  hardcoding means the UI cannot drift from what is actually enforced; the
  canary test in `PasswordChecklistTest` fails when a configured validator has
  no entry here.
* **advisory** — shown as advice, never enforced anywhere. These exist because
  we decided on 2026-08-17 to stop blocking signups on password composition
  (see the AUTH_PASSWORD_VALIDATORS comment in settings.py for the trade-off)
  while still telling people when they are choosing something weak.

An advisory rule must never render as an error. A person who chooses a common
password and submits anyway has made a decision we accepted; showing them a red
cross for a rule the server does not enforce would be a lie about what just
happened.

The checklist is a convenience layer regardless: nothing here blocks a
submission, and a check that cannot be evaluated faithfully in the browser is
allowed to be permissive (say "ok" where it might not be) but never stricter.
"""

from django.contrib.auth.password_validation import get_default_password_validators
from django.utils.translation import gettext_lazy as _


# Maps a validator class name to its checklist entry. `check` is the key the JS
# side dispatches on; keep the two in sync.
VALIDATOR_RULES = {
    "MinimumLengthValidator": {
        "id": "min-length",
        "check": "minLength",
        "label": _("At least %(min_length)d characters"),
    },
    "NumericPasswordValidator": {
        "id": "not-numeric",
        "check": "notNumeric",
        "label": _("Not entirely numbers"),
    },
    "CommonPasswordValidator": {
        "id": "not-common",
        "check": "notCommon",
        "label": _("Not a commonly used password"),
    },
    "UserAttributeSimilarityValidator": {
        "id": "not-similar",
        "check": "notSimilar",
        "label": _("Not too similar to your email or username"),
    },
}

# Shown as advice when the corresponding validator is NOT configured. If one of
# these is later added back to AUTH_PASSWORD_VALIDATORS, it moves from advice to
# enforced automatically and is not duplicated.
ADVISORY_RULES = (
    {
        "id": "not-common",
        "check": "notCommon",
        "validator": "CommonPasswordValidator",
        "label": _("Avoid a commonly used password"),
    },
    {
        "id": "not-similar",
        "check": "notSimilar",
        "validator": "UserAttributeSimilarityValidator",
        "label": _("Avoid reusing your email or username"),
    },
    {
        "id": "not-numeric",
        "check": "notNumeric",
        "validator": "NumericPasswordValidator",
        "label": _("Avoid a password of only numbers"),
    },
)


def _configured_validator_names():
    return {type(v).__name__ for v in get_default_password_validators()}


def password_checklist_rules():
    """Return enforced rules first, then advisory ones, in display order.

    Each rule is a dict with `id`, `check`, `label`, `advisory` (bool) and any
    parameters the client needs (e.g. `min_length`).
    """
    rules = []
    for validator in get_default_password_validators():
        spec = VALIDATOR_RULES.get(type(validator).__name__)
        if spec is None:
            continue
        rule = {"id": spec["id"], "check": spec["check"], "advisory": False}
        if spec["check"] == "minLength":
            min_length = getattr(validator, "min_length", 8)
            rule["min_length"] = min_length
            rule["label"] = spec["label"] % {"min_length": min_length}
        else:
            rule["label"] = spec["label"]
        rules.append(rule)

    configured = _configured_validator_names()
    for advisory in ADVISORY_RULES:
        if advisory["validator"] in configured:
            continue  # already covered as an enforced rule above
        rules.append({
            "id": advisory["id"],
            "check": advisory["check"],
            "label": advisory["label"],
            "advisory": True,
        })
    return rules


def unmapped_validators():
    """Return class names of configured validators with no checklist entry.

    Used by the canary test. An unmapped *enforced* validator means the form
    rejects passwords for a reason it never showed the user — the failure mode
    this whole change exists to prevent.
    """
    return sorted(_configured_validator_names() - set(VALIDATOR_RULES))
