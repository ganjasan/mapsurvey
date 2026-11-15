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
    # Closed list (owner 2026-11-14); `data.fields.LICENCES` names them.
    LICENCE_CHOICES = [
        ('ogl-uk-3.0', 'Open Government Licence v3.0'),
        ('cc-by-4.0', 'CC BY 4.0'),
        ('cc0-1.0', 'CC0 1.0'),
        ('dl-de-by-2.0', 'Datenlizenz Deutschland – Namensnennung 2.0'),
    ]
    # The DCAT-AP data themes (EU vocabulary) — what an open-data feed (#675) publishes.
    THEME_CHOICES = [
        ('AGRI', _('Agriculture, fisheries, forestry and food')),
        ('ECON', _('Economy and finance')),
        ('EDUC', _('Education, culture and sport')),
        ('ENER', _('Energy')),
        ('ENVI', _('Environment')),
        ('GOVE', _('Government and public sector')),
        ('HEAL', _('Health')),
        ('INTR', _('International issues')),
        ('JUST', _('Justice, legal system and public safety')),
        ('REGI', _('Regions and cities')),
        ('SOCI', _('Population and society')),
        ('TECH', _('Science and technology')),
        ('TRAN', _('Transport')),
    ]
    FREQUENCY_CHOICES = [
        ('as_needed', _('As needed')),
        ('daily', _('Daily')),
        ('weekly', _('Weekly')),
        ('monthly', _('Monthly')),
        ('quarterly', _('Quarterly')),
        ('yearly', _('Yearly')),
        ('never', _('Never updated')),
    ]
    licence = models.CharField(max_length=32, blank=True, default='', choices=LICENCE_CHOICES)
    theme = models.CharField(max_length=8, blank=True, default='', choices=THEME_CHOICES)
    maintainer = models.CharField(max_length=200, blank=True, default='',
                                  help_text=_('The team or role that keeps the dataset current.'))
    update_frequency = models.CharField(max_length=12, blank=True, default='', choices=FREQUENCY_CHOICES)
    # The field dictionary: [{'name', 'label', 'type', 'description', 'private'}] (data-upload
    # writes it, data-metadata edits it). A private field never leaves the dataset's own editor —
    # `data.fields` is the rule every output goes through.
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


class DatasetLink(models.Model):
    """A place that shows a dataset without a copy (change data-links, #670): a survey's reference
    layers (the CANONICAL survey, like layer ownership) or a Site map block. Every link is a
    "used by" record; `data.links` writes and reads them."""
    dataset = models.ForeignKey(Dataset, on_delete=models.CASCADE, related_name='links')
    survey = models.ForeignKey('survey.SurveyHeader', null=True, blank=True, on_delete=models.CASCADE,
                               related_name='dataset_links')
    site_block = models.ForeignKey('survey.SiteBlock', null=True, blank=True, on_delete=models.CASCADE,
                                   related_name='dataset_links')
    # The public fields the respondent's object card shows for this link ([] = all of them).
    fields = models.JSONField(default=list, blank=True)
    created_by = models.ForeignKey('auth.User', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at', 'id']
        constraints = [
            models.UniqueConstraint(fields=['dataset', 'survey'], condition=Q(survey__isnull=False),
                                    name='data_link_one_per_survey'),
            models.UniqueConstraint(fields=['site_block'], condition=Q(site_block__isnull=False),
                                    name='data_link_one_per_site_block'),
            models.CheckConstraint(
                condition=(Q(survey__isnull=False, site_block__isnull=True)
                           | Q(survey__isnull=True, site_block__isnull=False)),
                name='data_link_one_place'),
        ]


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
