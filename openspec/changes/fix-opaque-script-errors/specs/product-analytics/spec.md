# product-analytics Specification (delta)

## ADDED Requirements

### Requirement: Cross-origin scripts are loaded so their errors can be attributed
Every `<script src>` we ship that resolves to another origin SHALL carry `crossorigin="anonymous"`.
Without it a browser withholds the message, file and line of any exception thrown inside that script
and reports only the string `Script error.`, which makes the error untriageable and hides any real
defect behind it.

A script whose host does not send `access-control-allow-origin` SHALL NOT be given the attribute
blindly — with it the browser refuses to execute the script — so the header is checked before the
attribute is added.

#### Scenario: The analytics script is loaded with CORS
- **WHEN** a page including the analytics partial is rendered
- **THEN** the analytics script tag declares `crossorigin`

#### Scenario: A new external script without the attribute fails the build
- **WHEN** a template gains a `<script src>` pointing at another origin and omits `crossorigin`
- **THEN** the guard test fails, naming the template and the tag

#### Scenario: Local scripts are unaffected
- **WHEN** a template loads a script from our own origin or through `{% static %}`
- **THEN** the guard ignores it, since same-origin scripts need no CORS negotiation
