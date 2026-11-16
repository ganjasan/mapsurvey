"""Report tools (change reports-usage-api, #710): draft a report from a survey, write its blocks,
check it and publish it — the REST schemas and shared functions of `api.v1.reports`, every write
through `reports.services` with `Actor(surface='mcp')`. Publishing a report that shows quotes or
individual marks, and deleting one, need `confirm: true`."""
from typing import Optional
from uuid import UUID

from pydantic import Field

from api import scopes
from api.v1 import reports as v1
from api.v1.datasets import workspace_of

from ..errors import confirmation_required
from .common import actor
from .registry import args_model, tool

REPORT = (UUID, Field(description='The report uuid (from list_reports).'))
BLOCK = (int, Field(description='A block id from get_report.'))
CONFIRM = (bool, Field(False, description='Set to true only after the user confirmed this action in the conversation.'))


def _base(request):
    from survey.embedding import public_base_url
    return public_base_url(request)


def _values(args, *skip):
    """The arguments the caller actually sent, without the ids."""
    return {k: v for k, v in args.model_dump(exclude_unset=True).items() if k not in skip}


@tool(
    'list_reports',
    title='List reports',
    description=(
        'The reports of a workspace you may see: title, home survey, whether each is published, its address, '
        'tags and when it last changed. Filter by a tag.'
    ),
    scope=scopes.SURVEYS_READ, role='workspace member', read_only=True, idempotent=True,
    args=args_model('ListReportsArgs',
                    workspace=(Optional[str], Field(None, description='Workspace slug; needed when you belong to several.')),
                    tag=(Optional[str], Field(None, description='A workspace tag, by name or slug.'))),
)
def list_reports(request, args):
    from django.utils.text import slugify
    from reports.views import visible_reports
    p = request.principal
    org = workspace_of(p, args.workspace)
    slug = slugify(args.tag, allow_unicode=True) if args.tag else ''
    return {'items': [v1.report_out(r, _base(request)) for r in visible_reports(org, p.user)
                      if not slug or any(t.slug == slug for t in r.tags.all())]}


@tool(
    'get_report',
    title='Get a report',
    description=(
        'One report: its title and opening paragraph, settings, how often it was read, and every block in '
        'order with its id — the ids feed update_report_block and reorder_report_blocks.'
    ),
    scope=scopes.SURVEYS_READ, role='workspace member', read_only=True, idempotent=True,
    args=args_model('GetReportArgs', report=REPORT),
)
def get_report(request, args):
    return v1.report_out(v1.report_for(request.principal, args.report), _base(request), detail=True)


@tool(
    'create_report',
    title='Create a report',
    description=(
        'A new report, never published on creation. With `template` (summary, council, update, yousaid) it is '
        'drafted from the survey\'s answers by rules: who took part, a block per answered question, and '
        'candidate quotes as a hidden block for a person to pick from. Without it the report is empty. Reports '
        'are part of Pro.'
    ),
    scope=scopes.SURVEYS_WRITE, role='editor',
    args=args_model('CreateReportArgs', v1.ReportCreateIn),
)
def create_report(request, args):
    report = v1.create(request.principal, actor(request), workspace=args.workspace, survey=args.survey,
                       template=args.template, title=args.title)
    return v1.report_out(report, _base(request), detail=True)


@tool(
    'update_report',
    title='Update a report',
    description=(
        'Change a report\'s title, the line above it, the opening paragraph, the privacy threshold K (groups '
        'smaller than K are hidden; lowering it shows smaller groups of people), its tags or the sites that may '
        'embed it. Only the fields you send change.'
    ),
    scope=scopes.SURVEYS_WRITE, role='editor', idempotent=True,
    args=args_model('UpdateReportArgs', v1.ReportPatchIn, report=REPORT),
)
def update_report(request, args):
    report = v1.report_for(request.principal, args.report, edit=True)
    return v1.report_out(v1.save_settings(actor(request), report, _values(args, 'report')), _base(request), detail=True)


@tool(
    'add_report_block',
    title='Add a block to a report',
    description=(
        'Add a block at the end of a report. Written by you: heading (`text`), text (`html`, may hold tokens '
        '{responses} {opened} {finished} {marks:CODE} {respondents:CODE} that are filled from the home survey), '
        'numbers (`items` of value + label), quotes (`items` of text + source — publish a quote only when the '
        'person asked for it). Shown from answers: chart, map, objects or budget of one `question` code; '
        'crosstab of `rows` and `columns` question codes; engagement. Small groups are hidden in every data '
        'block. `show_marks` on a map shows individual marks, which can point at someone\'s home: off unless '
        'the person asks.'
    ),
    scope=scopes.SURVEYS_WRITE, role='editor',
    args=args_model('AddReportBlockArgs', v1.BlockIn, report=REPORT),
)
def add_report_block(request, args):
    report = v1.report_for(request.principal, args.report, edit=True)
    spec = {k: v for k, v in args.model_dump(exclude_none=True).items() if k != 'report'}
    return v1.add_block_from(actor(request), report, spec)


@tool(
    'update_report_block',
    title='Update a report block',
    description=(
        'Change a block\'s text, items, title, width (full or half — two halves in a row sit side by side) or '
        'whether it is hidden. Its type and its question stay: to show another question, add another block.'
    ),
    scope=scopes.SURVEYS_WRITE, role='editor', idempotent=True,
    args=args_model('UpdateReportBlockArgs', v1.BlockPatchIn, report=REPORT, block_id=BLOCK),
)
def update_report_block(request, args):
    report = v1.report_for(request.principal, args.report, edit=True)
    return v1.change_block(actor(request), report, args.block_id, _values(args, 'report', 'block_id'))


@tool(
    'delete_report_block',
    title='Delete a report block',
    description='Remove one block from a report. The answers it showed are not touched.',
    scope=scopes.SURVEYS_WRITE, role='editor', destructive=True,
    args=args_model('DeleteReportBlockArgs', report=REPORT, block_id=BLOCK),
)
def delete_report_block(request, args):
    from reports import services
    report = v1.report_for(request.principal, args.report, edit=True)
    services.delete_block(actor(request), v1.block_for(report, args.block_id))
    return {'deleted': args.block_id}


@tool(
    'reorder_report_blocks',
    title='Reorder report blocks',
    description='Put a report\'s blocks in a new order: every block id of the report, once.',
    scope=scopes.SURVEYS_WRITE, role='editor', idempotent=True,
    args=args_model('ReorderReportBlocksArgs', v1.OrderIn, report=REPORT),
)
def reorder_report_blocks(request, args):
    report = v1.report_for(request.principal, args.report, edit=True)
    return v1.report_out(v1.reorder(actor(request), report, args.order), _base(request), detail=True)


@tool(
    'get_report_checks',
    title='Check a report before publishing',
    description=(
        'What to look at before a report is published: under `people`, every quote written out and every map '
        'that shows individual marks; under `unfinished`, empty blocks, maps without a description, hidden '
        'blocks. Read `people` to the user before publish_report when `needs_confirm` is true.'
    ),
    scope=scopes.SURVEYS_READ, role='workspace member', read_only=True, idempotent=True,
    args=args_model('GetReportChecksArgs', report=REPORT),
)
def get_report_checks(request, args):
    return v1.checks_out(v1.report_for(request.principal, args.report))


@tool(
    'publish_report',
    title='Publish a report',
    description=(
        'Publish a report at its address, or take it down with `publish: false`. `visibility`: public (search '
        'engines may list it), unlisted (anyone with the link), workspace (signed-in members). `mode`: live '
        'follows new answers, frozen keeps the numbers of now. A report that shows quotes or individual marks '
        'needs `confirm: true` after the user read them (get_report_checks).'
    ),
    scope=scopes.SURVEYS_PUBLISH, role='editor', destructive=True, confirm=True,
    args=args_model('PublishReportArgs', v1.PublishIn, report=REPORT),
)
def publish_report(request, args):
    from reports.checks import run
    report = v1.report_for(request.principal, args.report, edit=True)
    if args.publish and not args.confirm and run(report).needs_ack:
        raise confirmation_required('Publishing a report that shows quotes or individual marks')
    report = v1.publish(actor(request), report, publish=args.publish, visibility=args.visibility,
                        mode=args.mode, confirm=args.confirm)
    return v1.report_out(report, _base(request), detail=True)


@tool(
    'freeze_report',
    title='Freeze a report',
    description=(
        'Freeze a report\'s numbers as they are now ("Data as of …"), or with `frozen: false` return it to '
        'numbers that follow new answers.'
    ),
    scope=scopes.SURVEYS_WRITE, role='editor', idempotent=True,
    args=args_model('FreezeReportArgs', v1.FreezeIn, report=REPORT),
)
def freeze_report(request, args):
    report = v1.report_for(request.principal, args.report, edit=True)
    return v1.report_out(v1.set_frozen(actor(request), report, args.frozen), _base(request), detail=True)


@tool(
    'delete_report',
    title='Delete a report',
    description=(
        'Delete a report with its blocks and pictures; its address stops working. The survey and its answers '
        'are not touched. Needs `confirm: true` after the user agreed; it cannot be undone.'
    ),
    scope=scopes.SURVEYS_DELETE, role='editor', destructive=True, confirm=True,
    args=args_model('DeleteReportArgs', report=REPORT, confirm=CONFIRM),
)
def delete_report(request, args):
    from reports import services
    report = v1.report_for(request.principal, args.report, edit=True)
    if not args.confirm:
        raise confirmation_required('Deleting a report')
    title, uuid = report.title, report.uuid
    services.delete_report(actor(request), report)
    return {'uuid': uuid, 'title': title, 'deleted': True}
