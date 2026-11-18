"""Reports in REST API v1 (change reports-usage-api, #710).

Create, read, write blocks, publish and freeze — every write through `reports.services` /
`reports.blocks` / `reports.drafting`, the functions the editor calls, behind the same two gates:
the workspace's API plan (`gates.require_pro_api`) and the Reports feature (`reports.gate.use`).
Scopes are the surveys': a report is what a survey's editor already works with; publishing needs
`surveys:publish`, deleting `surveys:delete`.
"""
from typing import List, Literal, Optional
from uuid import UUID

from ninja import Router, Schema, Status
from pydantic import ConfigDict, Field

from reports import blocks as report_blocks
from reports import services
from reports.models import Report, ReportBlock
from survey.models import Membership
from survey.permissions import get_org_membership

from .. import gates, scopes
from ..errors import CONFLICT, FORBIDDEN_ROLE, PRO_REQUIRED, VALIDATION, ApiError, not_found
from . import deps
from .auth import Bearer
from .datasets import workspace_of
from .docs import errors, list_errors

router = Router(tags=['Reports'])
READ = Bearer(scopes.SURVEYS_READ)
WRITE = Bearer(scopes.SURVEYS_WRITE)
PUBLISH = Bearer(scopes.SURVEYS_PUBLISH)
DELETE = Bearer(scopes.SURVEYS_DELETE)


class _In(Schema):
    model_config = ConfigDict(extra='forbid')


class ItemIn(_In):
    value: Optional[str] = Field(None, max_length=40, description='Key numbers: the figure, or a token such as {responses}.')
    label: Optional[str] = Field(None, max_length=120, description='Key numbers: what the figure counts.')
    text: Optional[str] = Field(None, max_length=1000, description='Quotes: the quote, published exactly as written.')
    source: Optional[str] = Field(None, max_length=160, description='Quotes: where it comes from.')


class BlockIn(_In):
    type: Literal['heading', 'text', 'numbers', 'quotes', 'chart', 'map', 'objects', 'budget', 'crosstab', 'engagement', 'compare']
    title: Optional[str] = Field(None, max_length=300, description='A title above the block.')
    width: Optional[Literal['full', 'half']] = Field(None, description='Two half-width blocks in a row sit side by side.')
    hidden: Optional[bool] = Field(None, description='Kept in the report, not shown on its page.')
    text: Optional[str] = Field(None, max_length=300, description='heading: the heading.')
    html: Optional[str] = Field(None, max_length=50000, description='text: rich text (sanitised). Tokens {responses}, {opened}, {finished}, {marks:CODE}, {respondents:CODE} are filled from the home survey.')
    items: Optional[List[ItemIn]] = Field(None, max_length=12, description='numbers: value + label; quotes: text + source.')
    note: Optional[str] = Field(None, max_length=2000, description='numbers: a line under them.')
    survey: Optional[UUID] = Field(None, description='The survey a data block shows; default: the report\'s home survey.')
    question: Optional[str] = Field(None, max_length=50, description='chart / map / objects / budget / compare: the question code.')
    other: Optional[UUID] = Field(None, description='compare: the other survey (another round) that has a question with the same code.')
    viz: Optional[Literal['auto', 'bar', 'pie', 'donut', 'table']] = Field(None, description='chart: how it is drawn.')
    rows: Optional[str] = Field(None, max_length=50, description='crosstab: the code of the question in the rows.')
    columns: Optional[str] = Field(None, max_length=50, description='crosstab: the code of the question in the columns.')
    show_marks: Optional[bool] = Field(None, description='map: the marks themselves instead of squares that count respondents. A mark can point at someone\'s home.')
    style: Optional[Literal['list', 'pull', 'cards']] = Field(None, description='quotes: one under another (list), each large (pull), or two columns (cards).')
    description: Optional[str] = Field(None, max_length=2000, description='map: what it shows, in a sentence (also read by screen readers).')


class BlockPatchIn(_In):
    title: Optional[str] = Field(None, max_length=300)
    width: Optional[Literal['full', 'half']] = None
    hidden: Optional[bool] = None
    text: Optional[str] = Field(None, max_length=300)
    html: Optional[str] = Field(None, max_length=50000)
    items: Optional[List[ItemIn]] = Field(None, max_length=12)
    note: Optional[str] = Field(None, max_length=2000)
    viz: Optional[Literal['auto', 'bar', 'pie', 'donut', 'table']] = None
    show_marks: Optional[bool] = None
    style: Optional[Literal['list', 'pull', 'cards']] = None
    description: Optional[str] = Field(None, max_length=2000)


class ReportCreateIn(_In):
    workspace: Optional[str] = Field(None, description='Workspace slug; needed when you belong to several.')
    survey: Optional[UUID] = Field(None, description='The home survey. With `template`, the survey the draft is made from.')
    template: Optional[Literal['summary', 'council', 'update', 'yousaid']] = Field(
        None, description='Draft the report from the survey\'s answers by rules: summary, council paper, engagement update, you said — we did. Left out: an empty report.')
    title: Optional[str] = Field(None, max_length=200)


class ReportPatchIn(_In):
    title: Optional[str] = Field(None, max_length=200)
    eyebrow: Optional[str] = Field(None, max_length=160, description='The line above the title.')
    lead: Optional[str] = Field(None, max_length=2000, description='The opening paragraph; tokens are filled.')
    k: Optional[int] = Field(None, ge=1, le=50, description='Groups smaller than K are hidden. 1 hides nothing.')
    tags: Optional[List[str]] = Field(None, max_length=10)
    embed_hosts: Optional[List[str]] = Field(None, max_length=50, description='Sites that may embed the report; empty = any.')


class PublishIn(_In):
    publish: bool = True
    visibility: Optional[Literal['public', 'unlisted', 'workspace']] = None
    mode: Optional[Literal['live', 'frozen']] = Field(None, description='live follows new answers; frozen keeps the numbers of now.')
    confirm: bool = Field(False, description='Required to publish a report that shows quotes or individual marks: the person confirmed having read them.')


class FreezeIn(_In):
    frozen: bool = True


class OrderIn(_In):
    order: List[int] = Field(description='Every block id of the report, in the new order.')


# ─── Helpers shared with the MCP tools ────────────────────────────────────────

def _member_org_ids(principal):
    qs = Membership.objects.filter(user=principal.user)
    if principal.organization is not None:
        qs = qs.filter(organization=principal.organization)
    return list(qs.values_list('organization_id', flat=True))


def _may_see(principal, report):
    from reports.views import visible_reports
    return any(r.pk == report.pk for r in visible_reports(report.organization, principal.user))


def _may_edit(principal, report):
    from survey.permissions import _check_survey_role, get_effective_survey_role
    membership = get_org_membership(principal.user, report.organization)
    if membership is None or membership.role not in ('owner', 'admin', 'editor'):
        return False
    if report.survey_id is None:
        return True
    return _check_survey_role(get_effective_survey_role(principal.user, report.survey), 'editor')


def require_reports(principal, organization):
    """The Reports feature for a write: by plan, a live trial, or starting the trial — else 403."""
    from reports import gate
    if not gate.use(organization, principal.user):
        raise ApiError(403, PRO_REQUIRED, 'Reports are part of Pro; this workspace\'s reports are read-only on its plan.',
                       organization=organization.slug, upgrade_url=gates.upgrade_url(organization))


def report_for(principal, uuid, edit=False):
    """The report the caller may see — 404 otherwise; 403 under the edit rule or the plan."""
    report = (Report.objects.select_related('survey', 'organization')
              .filter(uuid=uuid, organization_id__in=_member_org_ids(principal)).first())
    if report is None:
        raise not_found()
    gates.require_pro_api(principal, report.organization)
    if not _may_see(principal, report):
        raise not_found()
    if edit:
        if not _may_edit(principal, report):
            raise ApiError(403, FORBIDDEN_ROLE, 'Editing this report needs the editor role on it.', role='editor')
        require_reports(principal, report.organization)
    return report


def block_for(report, block_id):
    block = ReportBlock.objects.filter(pk=block_id, report=report).select_related('dataset__survey', 'view').first()
    if block is None:
        raise not_found()
    return block


def report_out(report, base='', detail=False):
    from reports.sources import attach_questions
    intro = report.intro or {}

    def en(value):
        return (value.get('en') or '') if isinstance(value, dict) else (value or '')

    out = {
        'uuid': str(report.uuid), 'title': report.title, 'workspace': report.organization.slug,
        'survey': str(report.survey.uuid) if report.survey_id else None,
        'published': report.is_published, 'visibility': report.visibility, 'mode': report.mode,
        'frozen_at': report.frozen_at, 'address': f'{base}/r/{report.slug}/',
        'tags': [t.name for t in report.tags.all()], 'updated_at': report.updated_at,
    }
    if detail:
        from reports.usage import summary
        usage = summary(report)
        out.update(eyebrow=en(intro.get('eyebrow')), lead=en(intro.get('body')), k=report.k_anonymity_threshold,
                   template=report.template, embed_hosts=list(report.embed_allowed_hosts or []),
                   readers={kind: usage[kind]['total'] for kind in ('view', 'embed', 'pdf')},
                   blocks=[report_blocks.describe(b)
                           for b in attach_questions(report.blocks.select_related('dataset__survey', 'view'))])
    return out


def refused(exc):
    """A refusal of the report services or of a block spec → the REST envelope."""
    if isinstance(exc, report_blocks.BlockRefused):
        return ApiError(422, VALIDATION, exc.message, fields={exc.field: [exc.message]})
    status = 409 if exc.code in ('ack_required', 'publish_survey_first') else 422
    code = CONFLICT if status == 409 else VALIDATION
    return ApiError(status, code, exc.message, fields={exc.code: [exc.message]})


def _base(request):
    from survey.embedding import public_base_url
    return public_base_url(request)


def save_settings(actor, report, values):
    """Change the settings `values` names (title, eyebrow, lead, k, tags, embed_hosts); the rest
    of the settings form keeps what it has."""
    intro = report.intro or {}

    def en(key):
        value = intro.get(key)
        return (value.get('en') or '') if isinstance(value, dict) else (value or '')

    try:
        services.update_settings(
            actor, report, visibility=report.visibility,
            intro_title=values.get('title', en('title')), intro_body=values.get('lead', en('body')),
            intro_eyebrow=values.get('eyebrow') if 'eyebrow' in values else None,
            embed_hosts='\n'.join(values['embed_hosts']) if values.get('embed_hosts') is not None else None,
            tags=values.get('tags'), show_response_count=report.show_response_count,
            show_participate_cta=report.show_participate_cta, show_on_thanks=report.show_on_thanks,
            feature_in_listing=report.feature_in_listing, k=values.get('k', report.k_anonymity_threshold),
            slug=report.slug)
    except services.ReportRefused as exc:
        raise refused(exc)
    return report


def create(principal, actor, workspace=None, survey=None, template=None, title=None):
    """Shared by REST and MCP: an empty report, or a draft from a survey's answers."""
    from reports import drafting
    from survey.versioning import canonical_of
    home = None
    if survey is not None:
        from .. import rights
        home = canonical_of(rights.survey_for(principal, survey, min_role='editor'))
        organization = home.organization
        gates.require_pro_api(principal, organization)
    else:
        organization = workspace_of(principal, workspace, editor=True)
    require_reports(principal, organization)
    if template:
        if home is None:
            raise ApiError(422, VALIDATION, 'A draft is made from a survey: name it.',
                           fields={'survey': ['required with template']})
        report = drafting.build_draft(actor, home, template)
        if title:
            save_settings(actor, report, {'title': title})
        return report
    return services.create_report(actor, organization, survey=home, title=title or 'Untitled report',
                                  visibility='workspace')


def publish(actor, report, publish=True, visibility=None, mode=None, confirm=False):
    try:
        services.set_published(actor, report, publish, ack=confirm, visibility=visibility, mode=mode)
    except services.ReportRefused as exc:
        raise refused(exc)
    report.refresh_from_db()
    return report


def set_frozen(actor, report, frozen):
    (services.freeze if frozen else services.unfreeze)(actor, report)
    report.refresh_from_db()
    return report


def reorder(actor, report, order):
    have = set(report.blocks.values_list('pk', flat=True))
    if set(order) != have or len(order) != len(have):
        raise ApiError(422, VALIDATION, 'Name every block of the report once.', fields={'order': ['every block id, once']})
    services.reorder_blocks(actor, report, order)
    return report


def add_block_from(actor, report, spec):
    spec = {key: str(value) if key in ('survey', 'other') else value for key, value in spec.items()}
    try:
        block = report_blocks.add(actor, report, spec)
    except report_blocks.BlockRefused as exc:
        raise refused(exc)
    return report_blocks.describe(block_for(report, block.pk))


def change_block(actor, report, block_id, spec):
    block = block_for(report, block_id)
    try:
        report_blocks.change(actor, block, spec)
    except report_blocks.BlockRefused as exc:
        raise refused(exc)
    return report_blocks.describe(block_for(report, block_id))


def checks_out(report):
    from reports.checks import run
    checks = run(report)

    def item(i):
        return {'key': i.key, 'message': i.message, 'block': i.block_id, 'quotes': list(i.detail)}
    return {'needs_confirm': checks.needs_ack, 'people': [item(i) for i in checks.privacy],
            'unfinished': [item(i) for i in checks.other]}


# ─── Routes ───────────────────────────────────────────────────────────────────

@router.get('/reports', response=dict, auth=READ, openapi_extra=list_errors())
def list_reports(request, workspace: Optional[str] = None, tag: Optional[str] = None):
    """The reports of a workspace that you may see, newest change first; `tag` keeps those carrying
    a workspace tag."""
    from django.utils.text import slugify
    from reports.views import visible_reports
    org = workspace_of(request.principal, workspace)
    slug = slugify(tag, allow_unicode=True) if tag else ''
    items = [report_out(r, _base(request)) for r in visible_reports(org, request.principal.user)
             if not slug or any(t.slug == slug for t in r.tags.all())]
    return {'items': items}


@router.post('/reports', response={201: dict}, auth=WRITE, openapi_extra=errors())
def create_report(request, payload: ReportCreateIn):
    """A new report: empty, or — with `template` — drafted from a survey's answers by rules (who
    took part, a block per answered question, quotes to pick from as a hidden block). Never
    published on creation."""
    report = create(request.principal, deps.actor(request), **payload.dict())
    return Status(201, report_out(report, _base(request), detail=True))


@router.get('/reports/{uuid}', response=dict, auth=READ, openapi_extra=errors())
def get_report(request, uuid: UUID):
    """One report: its opening, settings, how often it was read, and every block in order."""
    return report_out(report_for(request.principal, uuid), _base(request), detail=True)


@router.patch('/reports/{uuid}', response=dict, auth=WRITE, openapi_extra=errors())
def update_report(request, uuid: UUID, payload: ReportPatchIn):
    """Change the opening, the privacy threshold, the tags or the sites that may embed it."""
    report = report_for(request.principal, uuid, edit=True)
    return report_out(save_settings(deps.actor(request), report, payload.dict(exclude_unset=True)),
                      _base(request), detail=True)


@router.delete('/reports/{uuid}', response=dict, auth=DELETE, openapi_extra=errors())
def delete_report(request, uuid: UUID):
    """Delete a report and its blocks. The answers it shows are not touched."""
    report = report_for(request.principal, uuid, edit=True)
    services.delete_report(deps.actor(request), report)
    return {'deleted': str(uuid)}


@router.get('/reports/{uuid}/checks', response=dict, auth=READ, openapi_extra=errors())
def report_checks(request, uuid: UUID):
    """What to look at before publishing: quotes and maps of individual marks (`people`), and what
    looks unfinished. `needs_confirm` means publishing takes `confirm: true`."""
    return checks_out(report_for(request.principal, uuid))


@router.post('/reports/{uuid}/publish', response=dict, auth=PUBLISH, openapi_extra=errors(codes=(CONFLICT,)))
def publish_report(request, uuid: UUID, payload: PublishIn):
    """Publish (or, with `publish: false`, take down) a report. A report that shows quotes or
    individual marks answers 409 until `confirm` is true — read `/checks` to the person first."""
    report = report_for(request.principal, uuid, edit=True)
    return report_out(publish(deps.actor(request), report, **payload.dict()), _base(request), detail=True)


@router.post('/reports/{uuid}/freeze', response=dict, auth=WRITE, openapi_extra=errors())
def freeze_report(request, uuid: UUID, payload: FreezeIn):
    """Freeze the report's numbers as they are now, or return it to live numbers."""
    report = report_for(request.principal, uuid, edit=True)
    return report_out(set_frozen(deps.actor(request), report, payload.frozen), _base(request), detail=True)


@router.put('/reports/{uuid}/blocks/order', response=dict, auth=WRITE, openapi_extra=errors())
def reorder_blocks(request, uuid: UUID, payload: OrderIn):
    """Put the report's blocks in a new order: every block id, once."""
    report = report_for(request.principal, uuid, edit=True)
    return report_out(reorder(deps.actor(request), report, payload.order), _base(request), detail=True)


@router.post('/reports/{uuid}/blocks', response={201: dict}, auth=WRITE, openapi_extra=errors())
def add_block(request, uuid: UUID, payload: BlockIn):
    """Add a block at the end: something you write (heading, text, numbers, quotes) or something
    the answers show (chart, map, objects, budget of one question; crosstab of two; engagement).
    Small groups are hidden in every data block."""
    report = report_for(request.principal, uuid, edit=True)
    return Status(201, add_block_from(deps.actor(request), report, payload.dict(exclude_none=True)))


@router.patch('/reports/{uuid}/blocks/{block_id}', response=dict, auth=WRITE, openapi_extra=errors())
def update_block(request, uuid: UUID, block_id: int, payload: BlockPatchIn):
    """Change a block's text, items, title, width or visibility. Its type and its question stay:
    to show another question, add another block."""
    report = report_for(request.principal, uuid, edit=True)
    return change_block(deps.actor(request), report, block_id, payload.dict(exclude_unset=True))


@router.delete('/reports/{uuid}/blocks/{block_id}', response=dict, auth=WRITE, openapi_extra=errors())
def delete_block(request, uuid: UUID, block_id: int):
    """Remove a block from the report."""
    report = report_for(request.principal, uuid, edit=True)
    services.delete_block(deps.actor(request), block_for(report, block_id))
    return {'deleted': block_id}
