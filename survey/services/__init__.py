"""The one write path for survey structure and lifecycle (change rest-api-v1, #380).

Everything that creates, edits, deletes or reorders a survey, section or
question on a creator's behalf, and every lifecycle step (publish, close,
unpublished changes), lives here once. The editor views and the REST API
(`api/v1/`) both call these functions; neither writes those models itself, so
the rules -- `coerce_creator_html`, `clean_redirect_url`, the live-survey
content/structure split, content screening, the audit trail -- cannot drift
between the two.

Three conventions every module follows:

- a service takes an `Actor` and plain values, never a request;
- input is validated by the same Django form the editor uses, bound to a
  plain dict, BEFORE anything is written, and the whole operation runs in one
  transaction;
- refusals are `errors.ServiceError` subclasses, which each surface maps to
  its own response (the editor to what it always answered, the API to its
  envelope).
"""
