"""`import_survey`: a whole survey in one call, as the job the web and REST
imports enqueue (design D9). The request zips the document and stores it; the
Celery worker parses it (`run_survey_import`), records the outcome on the job
and deletes the archive."""
import io
import json
import zipfile
from typing import Optional

from django.conf import settings
from django.core.files.base import ContentFile
from pydantic import Field

from survey.models import SurveyImportJob
from survey.tasks import run_survey_import

from api import limits, scopes
from api.errors import VALIDATION, ApiError, not_found
from api.v1 import out
from api.v1.surveys import workspace_for

from .registry import args_model, tool


@tool(
    'import_survey',
    title='Import a survey document',
    description=(
        'Create a whole survey from one document: the `survey.json` of Mapsurvey\'s backup format (version '
        '"1.0", a `survey` object with `name`, `available_languages`, `sections` with `questions`). The import '
        'runs in the background; the result is a job -- poll get_import_job until its status is done or '
        'failed. Name the workspace by its slug when you belong to several.'
    ),
    scope=scopes.SURVEYS_WRITE, role='workspace editor',
    args=args_model(
        'ImportSurveyArgs',
        survey_json=(dict, Field(description='The survey.json document as an object, not a string.')),
        workspace=(Optional[str], Field(None, description='Workspace slug.')),
    ),
)
def import_survey(request, args):
    p = request.principal
    organization = workspace_for(p, args.workspace)
    text = json.dumps(args.survey_json, ensure_ascii=False)
    if len(text.encode('utf-8')) > settings.MCP_IMPORT_MAX_BYTES:
        raise ApiError(422, VALIDATION, 'The document is too large for this tool.',
                       fields={'survey_json': [f'Larger than {settings.MCP_IMPORT_MAX_BYTES} bytes.']})
    name = str((args.survey_json.get('survey') or {}).get('name') or 'survey') if isinstance(
        args.survey_json.get('survey'), dict) else 'survey'
    limits.hit(p, 'survey_import')
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('survey.json', text)
    job = SurveyImportJob.objects.create(
        user=p.user, organization=organization, original_name=f'{name[:240]}.json',
        file=ContentFile(buffer.getvalue(), name='import.zip'),
    )
    run_survey_import.delay(job.pk)
    return out.import_job(job)


@tool(
    'get_import_job',
    title='Check an import job',
    description='One of your import jobs: status (queued, running, done, failed), the survey it made, warnings.',
    scope=scopes.SURVEYS_READ, role='-', read_only=True, idempotent=True,
    args=args_model('GetImportJobArgs', job_id=(int, Field(description='The job id import_survey returned.'))),
)
def get_import_job(request, args):
    job = SurveyImportJob.objects.filter(pk=args.job_id, user=request.principal.user).select_related('survey').first()
    if job is None:
        raise not_found()
    return out.import_job(job)
