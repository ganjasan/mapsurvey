"""The dataset registry (change data-catalogue, #667; ADR-001 §4).

A `Dataset` is a registry row over data that lives elsewhere — a reference layer, a shared map,
a survey's answers to one geo question, a survey's respondent rows. Nothing moves into it; it
gives every place dataset of a workspace one identity that the catalogue, the dataset page,
"From Data" links, versions, views, tags and the API hang off. Rows are created and dropped by
`data.datasets.sync(org)`.
"""
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _


class Dataset(models.Model):
    KIND_LAYER = 'layer'            # a creator's reference layer: uploaded or drawn objects
    KIND_SHARED_MAP = 'shared_map'  # a layer materialised from respondents' answers
    KIND_ANSWERS = 'answers'        # a survey's answers to one top-level geo question (by code)
    KIND_RESPONSES = 'responses'    # a survey's respondent rows
    KIND_CHOICES = [
        (KIND_LAYER, _('Layer')),
        (KIND_SHARED_MAP, _('Shared map')),
        (KIND_ANSWERS, _('Answers')),
        (KIND_RESPONSES, _('Responses')),
    ]
    LAYER_KINDS = (KIND_LAYER, KIND_SHARED_MAP)
    COLLECTED_KINDS = (KIND_ANSWERS, KIND_RESPONSES)

    PRIVACY_PUBLIC = 'public'
    PRIVACY_AGGREGATED = 'aggregated'
    PRIVACY_PRIVATE = 'private'
    PRIVACY_CHOICES = [
        (PRIVACY_PUBLIC, _('Public')),
        (PRIVACY_AGGREGATED, _('Aggregated')),
        (PRIVACY_PRIVATE, _('Private')),
    ]

    organization = models.ForeignKey('survey.Organization', on_delete=models.CASCADE, related_name='datasets')
    kind = models.CharField(max_length=12, choices=KIND_CHOICES)
    layer = models.ForeignKey('survey.SurveyMapLayer', null=True, blank=True, on_delete=models.CASCADE,
                              related_name='datasets')
    survey = models.ForeignKey('survey.SurveyHeader', null=True, blank=True, on_delete=models.CASCADE,
                               related_name='datasets',
                               help_text=_('The canonical survey: collected kinds span its versions.'))
    question_code = models.CharField(max_length=50, blank=True, default='')
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, default='')
    privacy_class = models.CharField(max_length=12, choices=PRIVACY_CHOICES, default=PRIVACY_PRIVATE)
    licence = models.CharField(max_length=32, blank=True, default='')
    # The field dictionary (change data-upload): [{'name', 'label', 'type', 'private'}]. A private
    # field never leaves the dataset's own editor (enforced from #669).
    fields = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name', 'id']
        constraints = [
            models.UniqueConstraint(fields=['layer'], condition=Q(layer__isnull=False),
                                    name='data_dataset_one_per_layer'),
            models.UniqueConstraint(fields=['survey', 'kind', 'question_code'],
                                    condition=Q(kind__in=('answers', 'responses')),
                                    name='data_dataset_one_per_collected_source'),
            models.CheckConstraint(
                condition=(Q(kind__in=('layer', 'shared_map'), layer__isnull=False)
                           | Q(kind__in=('answers', 'responses'), survey__isnull=False)),
                name='data_dataset_source_matches_kind'),
        ]

    def __str__(self):
        return f'{self.name} ({self.kind})'


def data_import_key(instance, filename):
    """data_imports/<uuid4><ext> on the PRIVATE tier: a random key, never the creator's
    filename, deleted when the job finishes."""
    import os
    import uuid
    ext = os.path.splitext(filename or '')[1].lower()[:10]
    return f'data_imports/{uuid.uuid4().hex}{ext}'


def _private_storage():
    from survey.models import _private_media_storage
    return _private_media_storage()


class DataImportJob(models.Model):
    """A file being turned into a workspace dataset (change data-upload, #668). The upload view
    stores the file and enqueues `data.tasks.run_data_import`; the catalogue shows the card."""
    STATUS_CHOICES = [('queued', 'queued'), ('running', 'running'), ('done', 'done'), ('failed', 'failed')]

    organization = models.ForeignKey('survey.Organization', on_delete=models.CASCADE, related_name='data_imports')
    user = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='data_imports')
    file = models.FileField(upload_to=data_import_key, storage=_private_storage, max_length=500, blank=True)
    original_name = models.CharField(max_length=255)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='queued', db_index=True)
    dataset = models.ForeignKey(Dataset, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    report = models.JSONField(default=dict, blank=True)
    error = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
