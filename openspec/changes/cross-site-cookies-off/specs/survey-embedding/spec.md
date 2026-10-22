## MODIFIED Requirements

### Requirement: Session and CSRF cookies survive inside a cross-site frame
A survey framed by another site SHALL keep its session through `EmbedSessionMiddleware`'s
cookie-less carrier. Cross-site cookie attributes are opt-in: when the setting
`CROSS_SITE_COOKIES` is on (read from the environment; default off), the session cookie and the
CSRF cookie SHALL be set with `SameSite=None`, `Secure` and `Partitioned`. When it is off they
SHALL keep Django's defaults, and a request whose raw `Cookie` header carries two values for the
session or CSRF cookie SHALL be answered with a deletion of the partitioned variant of that
cookie (`Max-Age=0`, `Secure`, `SameSite=None; Partitioned`) unless the response already sets
that cookie. The sweep SHALL never reject a request. No other cookie SHALL be changed. The CSRF
middleware's Origin/Referer verification SHALL remain in force.

#### Scenario: Cookies carry cross-site attributes when the switch is on
- **WHEN** `CROSS_SITE_COOKIES` is on and a respondent opens a survey section
- **THEN** the `Set-Cookie` header for `sessionid` contains `SameSite=None`, `Secure` and `Partitioned`
- **AND** the `Set-Cookie` header for `csrftoken` contains the same three attributes

#### Scenario: Cookies keep defaults by default
- **WHEN** `CROSS_SITE_COOKIES` is unset and a respondent opens a survey section
- **THEN** the `sessionid` cookie is `SameSite=Lax` and carries neither `Secure` nor `Partitioned`

#### Scenario: Stale partitioned cookie is deleted
- **WHEN** `CROSS_SITE_COOKIES` is off and a request arrives with `Cookie: csrftoken=a; csrftoken=a` to a URL whose response does not set `csrftoken`
- **THEN** the response carries `Set-Cookie: csrftoken=; Max-Age=0; …; Secure; SameSite=None; Partitioned`

#### Scenario: A response that sets the cookie is left alone
- **WHEN** the same duplicate arrives on a survey section page, which sets `csrftoken` itself
- **THEN** the response's `csrftoken` cookie carries the value Django read and no deletion

#### Scenario: A single cookie costs nothing
- **WHEN** a request carries one `csrftoken` and one `sessionid`
- **THEN** the response carries no deletion for either

#### Scenario: Cross-site forgery is still rejected
- **WHEN** a POST to a section URL arrives with a valid session cookie but an `Origin` header naming another site
- **THEN** the response is 403
