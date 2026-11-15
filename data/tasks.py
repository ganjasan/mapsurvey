"""Background jobs of the Data module (change data-upload, #668)."""
import logging
import os
import shutil
import tempfile

from celery import shared_task

logger = logging.getLogger(__name__)

FREE_MAX_BYTES = 10 * 1024 * 1024
PRO_MAX_BYTES = 50 * 1024 * 1024
FREE_MAX_FEATURES = 5000
PRO_MAX_FEATURES = 100000


def limits_for(org):
    """(max bytes, max features) of an upload for the workspace's plan (owner defaults 2026-11-14)."""
    from billing import entitlements
    try:
        pro = entitlements.for_organization(org).is_pro
    except Exception:  # noqa: BLE001 — a billing hiccup must not block Free-sized uploads
        pro = False
    return (PRO_MAX_BYTES, PRO_MAX_FEATURES) if pro else (FREE_MAX_BYTES, FREE_MAX_FEATURES)


def import_file(job):
    """Turn the job's file into a workspace dataset; returns (dataset, report). Raises
    ImportRefused for a creator-facing refusal."""
    from data.imports import ImportRefused, open_source
    from data.models import Dataset
    from survey.layers import objects_from_features, rebuild_layer
    from survey.models import SurveyMapLayer

    workdir = tempfile.mkdtemp(prefix='data-job-')
    ext = os.path.splitext(job.original_name)[1].lower()
    local = os.path.join(workdir, 'upload' + ext)
    with job.file.open('rb') as src, open(local, 'wb') as dst:
        shutil.copyfileobj(src, dst)
    try:
        source = open_source(local, job.original_name)
        profile = source.profile()
        _max_bytes, max_features = limits_for(job.organization)
        located = profile['count'] - profile['no_location']
        if located == 0:
            raise ImportRefused('No row of the file has a location.')
        if located > max_features:
            raise ImportRefused(f'The file has {located} features; the limit for this workspace is {max_features}.')
        name = os.path.splitext(os.path.basename(job.original_name))[0][:100] or 'Dataset'
        from django.db import transaction
        # One transaction: a catalogue load's sync() in another request must never see the layer
        # before its dataset row exists (it would create the row itself and this one would clash).
        with transaction.atomic():
            layer = SurveyMapLayer.objects.create(survey=None, organization=job.organization, name=name,
                                                  geojson='', key_field=profile['key_field'])
            result = objects_from_features(
                layer, source.features(),
                mapping={'key': profile['key_field']} if profile['key_field'] else None)
            rebuild_layer(layer)
            dataset, _created = Dataset.objects.update_or_create(
                layer=layer, defaults=dict(organization=job.organization, kind=Dataset.KIND_LAYER, name=name,
                                           privacy_class=Dataset.PRIVACY_PRIVATE, fields=profile['fields']))
            from data.models import DatasetVersion
            DatasetVersion.objects.get_or_create(dataset=dataset, number=1, defaults=dict(
                created_by=job.user, added=result['created']))
        report = {
            'created': result['created'],
            'no_location': profile['no_location'],
            'duplicates': len(result['collisions']),
            'duplicate_keys': result['collisions'][:20],
            'crs': profile['crs'],
            'private_fields': [f['name'] for f in profile['fields'] if f['private']],
            'fields': len(profile['fields']),
        }
        return dataset, report
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


@shared_task(bind=True)
def run_data_import(self, job_id):
    """Import one DataImportJob, once: a redelivered message finds the row past `queued`. A refusal
    is the creator's to read on the card; anything else is marked failed and re-raised so the
    task_failure receiver reports it. The uploaded file is deleted either way."""
    from django.utils import timezone
    from data.imports import ImportRefused
    from data.models import DataImportJob

    try:
        job = DataImportJob.objects.select_related('organization', 'user').get(pk=job_id)
    except DataImportJob.DoesNotExist:
        logger.warning('data import %s: row gone before the worker got to it', job_id)
        return
    if job.status != 'queued':
        return
    job.status = 'running'
    job.save(update_fields=['status'])
    try:
        dataset, report = import_file(job)
        job.dataset, job.report, job.status = dataset, report, 'done'
    except ImportRefused as exc:
        job.status, job.error = 'failed', str(exc)
    except Exception:
        job.status, job.error = 'failed', 'The file could not be imported. Try again or contact support.'
        job.finished_at = timezone.now()
        job.save(update_fields=['status', 'error', 'finished_at'])
        _delete_file(job)
        raise
    job.finished_at = timezone.now()
    job.save(update_fields=['status', 'error', 'dataset', 'report', 'finished_at'])
    _delete_file(job)


def _local_copy(job):
    """(workdir, local path) of the job's file — GDAL needs a path, the storage may be S3."""
    workdir = tempfile.mkdtemp(prefix='data-version-')
    local = os.path.join(workdir, 'upload' + os.path.splitext(job.original_name)[1].lower())
    with job.file.open('rb') as src, open(local, 'wb') as dst:
        shutil.copyfileobj(src, dst)
    return workdir, local


@shared_task(bind=True)
def run_data_version(self, job_id, apply=False):
    """A new version of `job.target` (change data-versions): `apply=False` computes the diff and
    stops at `preview` keeping the file; `apply=True` (status `applying`, set by the confirm)
    writes it and deletes the file. Once per state: a redelivered message finds the row moved on."""
    from django.utils import timezone
    from data import versions
    from data.imports import ImportRefused, open_source
    from data.models import DataImportJob

    job = DataImportJob.objects.select_related('organization', 'user', 'target__layer').filter(pk=job_id).first()
    if job is None or job.target is None:
        return
    expected = 'applying' if apply else 'queued'
    if job.status != expected:
        return
    if not apply:
        job.status = 'running'
        job.save(update_fields=['status'])
    workdir = None
    try:
        workdir, local = _local_copy(job)
        source = open_source(local, job.original_name)
        if apply:
            version = versions.apply(job.target, source, user=job.user, note=job.note)
            job.status, job.dataset = 'done', job.target
            job.report = {**job.report, 'version': version.number}
        else:
            job.report = versions.preview(job.target, source)
            job.status = 'preview'
    except (ImportRefused, versions.VersionRefused) as exc:
        job.status, job.error = 'failed', exc.message if hasattr(exc, 'message') else str(exc)
    except Exception:
        job.status, job.error = 'failed', 'The file could not be read. Try again or contact support.'
        job.finished_at = timezone.now()
        job.save(update_fields=['status', 'error', 'finished_at'])
        _delete_file(job)
        raise
    finally:
        if workdir:
            shutil.rmtree(workdir, ignore_errors=True)
    if job.status != 'preview':
        job.finished_at = timezone.now()
    job.save(update_fields=['status', 'error', 'dataset', 'report', 'finished_at'])
    if job.status in ('done', 'failed'):
        _delete_file(job)


def _delete_file(job):
    try:
        if job.file:
            job.file.delete(save=False)
            type(job).objects.filter(pk=job.pk).update(file='')
    except Exception:  # noqa: BLE001
        logger.exception('data import %s: could not delete the uploaded file', job.pk)
