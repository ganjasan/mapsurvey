"""Model rows → response bodies. Read-only; nothing here writes."""
from django.conf import settings
from django.urls import reverse

from survey.content_screening import pending_review_for
from survey.models import Question
from survey.services.groups import groups_of
from survey.services.sections import ordered


def _abs(path):
    return settings.SITE_URL.rstrip('/') + path


def _map_start(obj):
    point = obj.start_map_postion
    if point is None:
        return None
    return {'lat': point.y, 'lng': point.x, 'zoom': obj.start_map_zoom or 12}


def survey(obj):
    draft = None if obj.is_draft_copy else obj.get_draft_copy()
    return {
        'uuid': obj.uuid,
        'name': obj.name,
        'status': obj.status,
        'workspace': obj.organization.slug if obj.organization_id else None,
        'languages': list(obj.available_languages or []),
        'redirect_url': obj.redirect_url,
        'visibility': obj.visibility,
        'version': obj.version_number,
        'is_unpublished_changes': obj.is_draft_copy,
        'live_survey': obj.published_version.uuid if obj.is_draft_copy else None,
        'unpublished_changes': draft.uuid if draft is not None else None,
        'review': 'pending' if pending_review_for(obj) is not None else None,
        'url': _abs(reverse('survey', args=[str(obj.uuid)])),
        'created_at': obj.created_at,
        'updated_at': obj.updated_at,
    }


def survey_detail(obj):
    thanks = obj.thanks_html or {}
    if isinstance(thanks, str):
        langs = obj.available_languages or ['en']
        thanks = {langs[0]: thanks}
    return {
        **survey(obj),
        'thanks_html': thanks,
        'basemaps': list(obj.basemaps or []),
        'default_basemap': obj.default_basemap or '',
        'show_branding': obj.show_branding,
        'map_start': _map_start(obj),
        'use_geolocation': obj.use_geolocation,
        'sections': [s.pk for s in ordered(obj)],
    }


def section(obj, position=None):
    if position is None:
        position = [s.pk for s in ordered(obj.survey_header)].index(obj.pk)
    return {
        'id': obj.pk,
        'code': obj.code,
        'name': obj.name,
        'title': obj.title,
        'subheading': obj.subheading,
        'layout': obj.layout,
        'next_label': obj.next_label,
        'position': position,
        'visibility_rule': obj.visibility_rule,
        'map_start': _map_start(obj),
        'use_geolocation': obj.use_geolocation,
        'translations': {
            t.language: {'title': t.title, 'subheading': t.subheading, 'next_label': t.next_label}
            for t in obj.translations.all()
        },
        'questions': list(
            Question.objects.filter(survey_section=obj, parent_question_id__isnull=True)
            .order_by('order_number', 'id').values_list('pk', flat=True)),
        'groups': list(groups_of(obj).values_list('pk', flat=True)),
    }


def group(obj):
    return {
        'id': obj.pk,
        'code': obj.code,
        'section_id': obj.survey_section_id,
        'parent_id': obj.parent_question_id,
        'order': obj.order_number,
        'title': obj.title or '',
        'description': obj.description or '',
        'display_style': obj.display_style,
        'visibility_rule': obj.visibility_rule,
        'question_ids': [q.pk for q in obj.members()],
        'translations': {t.language: {'title': t.title, 'description': t.description}
                         for t in obj.translations.all()},
    }


def question(obj):
    return {
        'id': obj.pk,
        'code': obj.code,
        'section_id': obj.survey_section_id,
        'parent_id': obj.parent_question_id_id,
        'group_id': obj.group_id,
        'order': obj.order_number,
        'name': obj.name or '',
        'subtext': obj.subtext,
        'input_type': obj.input_type,
        'required': obj.required,
        'choices': obj.choices,
        'validation_settings': obj.validation_settings or {},
        'color': obj.color,
        'icon_class': obj.icon_class,
        'display_style': obj.display_style,
        'visibility_rule': obj.visibility_rule,
        'layer_id': obj.layer_id,
        'min_objects': obj.min_objects,
        'share_with_respondents': obj.share_with_respondents,
        'translations': {t.language: {'name': t.name, 'subtext': t.subtext} for t in obj.translations.all()},
        'subquestions': list(
            Question.objects.filter(parent_question_id=obj).order_by('order_number', 'id')
            .values_list('pk', flat=True)),
    }


def layer(obj, survey_obj):
    return {
        'id': obj.pk,
        'name': obj.name,
        'source': obj.source,
        'color': obj.color,
        'position': obj.position,
        'feature_count': obj.feature_count,
        'property_names': list(obj.property_names or []),
        'geojson_url': _abs(reverse('api_v1:layer_geojson', args=[str(survey_obj.uuid), obj.pk])),
    }


def import_job(job):
    return {
        'id': job.pk,
        'status': job.status,
        'original_name': job.original_name,
        'survey': job.survey.uuid if job.survey_id else None,
        'warnings': list(job.warnings or []),
        'error': job.error or None,
        'created_at': job.created_at,
        'finished_at': job.finished_at,
    }

