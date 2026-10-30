## MODIFIED Requirements

### Requirement: The form is a Pro feature; Free organisations see the offer
`/org/<slug>/help/` SHALL render the request form for members of organisations for which
`billing.trial.may(org, "pro_help")` is true (the plan includes it, a live trial has a `pro_help`
remainder, or the workspace is startable — then with one sentence saying that sending the request
starts the workspace's free Pro trial). For members of other organisations it SHALL render the
service description with, for the owner, the "Try Pro" control when the trial state is `available`
(posting to the claim endpoint with `next` set to the help page) or an Upgrade link otherwise, and
for other members a "ask your organisation owner" note; when the trial's `pro_help` allowance is
used up or the trial has expired the page SHALL say so in one sentence. It SHALL reject POSTs from
organisations for which `may` is false with HTTP 403. A valid request from an organisation whose
plan lacks `pro_help` SHALL go through `billing.trial.use(org, "pro_help", actor)` before it is
saved — starting a startable trial — and if that returns false nothing is stored and the Free view
renders.

#### Scenario: Pro member opens the page
- **WHEN** an editor of a Pro organisation opens `/org/<slug>/help/`
- **THEN** the request form is rendered

#### Scenario: Startable member opens the page
- **WHEN** a member of a Free organisation without a grant, whose owner has not used a trial, opens the page
- **THEN** the request form is rendered with the sentence that sending it starts the free Pro trial, and no grant exists

#### Scenario: Startable member submits
- **WHEN** that member submits a valid request
- **THEN** a `ProHelpRequest` row exists, the trial grant exists with `trigger = "pro_help"`, and its `pro_help` allowance reads 1 used

#### Scenario: Free owner whose trial ended opens the page
- **WHEN** the owner of a Free organisation whose trial expired opens the page
- **THEN** the service description, the "trial ended" sentence and the Upgrade link are rendered and no form

#### Scenario: Free POST
- **WHEN** a member of a Free organisation that is not startable and has no live trial POSTs to the page
- **THEN** the response is HTTP 403 and nothing is stored

#### Scenario: Trial member submits
- **WHEN** an editor of a Free organisation whose trial has 1 `pro_help` left submits a valid request
- **THEN** a `ProHelpRequest` row exists, the allowance reads 0 left, and the page then renders the service description with the "trial used" sentence instead of the form

## ADDED Requirements

### Requirement: The service is named by what the creator gets, beside free support
The `pro_help` feature label SHALL be "Advice on your survey and results" (one registry string,
`billing/features.py`, followed by the plan cards, Plan & billing, `/pricing/`, the landings and
the help centre). Every menu entry point to `/org/<slug>/help/` (the "?" menu, the account menus of
both base templates) SHALL use that label with `{% pro_badge org "pro_help" %}`, and SHALL sit
below a free entry "Suggest an idea or report a bug" without a Pro mark, which opens the support
chat (`openSupportChat(event, {topic: 'feature_request'})`) or, without the chat, the support e-mail.
The help page SHALL say in one line what the advice covers — a check of the survey before launch,
how to reach respondents, reading the results — and that hands-on work (building a survey, an
analysis kit, a written report) is quoted separately. No surface SHALL describe `pro_help` as
"reports included".

#### Scenario: Menu on a Free workspace
- **WHEN** a member of a startable Free workspace opens the "?" menu
- **THEN** "Suggest an idea or report a bug" is listed without a Pro mark, followed by "Advice on your survey and results" with the "Pro · free to try" mark

#### Scenario: Ideas stay free
- **WHEN** a member of a Free workspace whose trial has expired clicks "Suggest an idea or report a bug"
- **THEN** the support chat opens with the topic set, and no Pro refusal is shown
