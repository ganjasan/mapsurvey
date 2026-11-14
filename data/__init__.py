"""The Data module (Platform Vision v0.4, ADR-001): the workspace's one home for place data.

Every read of survey sessions goes through `data.scope`; the guard
`survey.tests.test_session_scope.SessionFilterGuardTest` fails on a new hand-written copy
anywhere else. Models arrive with the dataset registry (#667); until then this is a plain
package, not an installed app.
"""
