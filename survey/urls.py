from django.urls import path, re_path

from . import views
from . import editor_views
from . import analytics_views
from . import share_views
from . import org_views

urlpatterns = [
    path('', views.index, name='index'),
    path('editor/', views.editor, name='editor'),
    path('editor/export/<uuid:survey_uuid>/', views.export_survey, name='export_survey'),
    path('editor/import/', views.import_survey, name='import_survey'),
    path('editor/delete/<uuid:survey_uuid>/', views.delete_survey, name='delete_survey'),

    # Organization management
    path('org/new/', org_views.org_create, name='org_create'),
    path('org/switch/', org_views.switch_org, name='org_switch'),
    re_path(r'^org/(?P<slug>[-.\w]+)/settings/$', org_views.org_settings, name='org_settings'),
    re_path(r'^org/(?P<slug>[-.\w]+)/members/$', org_views.org_members, name='org_members'),
    re_path(r'^org/(?P<slug>[-.\w]+)/members/(?P<user_id>\d+)/role/$', org_views.org_change_role, name='org_change_role'),
    re_path(r'^org/(?P<slug>[-.\w]+)/members/(?P<user_id>\d+)/remove/$', org_views.org_remove_member, name='org_remove_member'),
    re_path(r'^org/(?P<slug>[-.\w]+)/invite/$', org_views.org_send_invitation, name='org_send_invitation'),
    path('invitations/<uuid:token>/accept/', org_views.accept_invitation, name='accept_invitation'),

    # WYSIWYG survey editor
    path('editor/surveys/new/', editor_views.editor_survey_create, name='editor_survey_create'),
    path('editor/surveys/<uuid:survey_uuid>/', editor_views.editor_survey_detail, name='editor_survey_detail'),
    path('editor/surveys/<uuid:survey_uuid>/settings/', editor_views.editor_survey_settings, name='editor_survey_settings'),
    path('editor/surveys/<uuid:survey_uuid>/sections/new/', editor_views.editor_section_create, name='editor_section_create'),
    path('editor/surveys/<uuid:survey_uuid>/sections/<int:section_id>/', editor_views.editor_section_detail, name='editor_section_detail'),
    path('editor/surveys/<uuid:survey_uuid>/sections/<int:section_id>/delete/', editor_views.editor_section_delete, name='editor_section_delete'),
    path('editor/surveys/<uuid:survey_uuid>/sections/reorder/', editor_views.editor_sections_reorder, name='editor_sections_reorder'),
    path('editor/surveys/<uuid:survey_uuid>/sections/<int:section_id>/questions/new/', editor_views.editor_question_create, name='editor_question_create'),
    path('editor/surveys/<uuid:survey_uuid>/questions/<int:question_id>/edit/', editor_views.editor_question_edit, name='editor_question_edit'),
    path('editor/surveys/<uuid:survey_uuid>/questions/<int:question_id>/preview/', editor_views.editor_question_preview, name='editor_question_preview'),
    path('editor/surveys/<uuid:survey_uuid>/questions/<int:question_id>/delete/', editor_views.editor_question_delete, name='editor_question_delete'),
    path('editor/surveys/<uuid:survey_uuid>/questions/reorder/', editor_views.editor_questions_reorder, name='editor_questions_reorder'),
    path('editor/surveys/<uuid:survey_uuid>/questions/<int:parent_id>/subquestions/new/', editor_views.editor_subquestion_create, name='editor_subquestion_create'),
    path('editor/surveys/<uuid:survey_uuid>/sections/<int:section_id>/map/', editor_views.editor_section_map_picker, name='editor_section_map_picker'),
    path('editor/surveys/<uuid:survey_uuid>/preview/<str:section_name>/', editor_views.editor_section_preview, name='editor_section_preview'),
    path('editor/surveys/<uuid:survey_uuid>/transition/', editor_views.editor_survey_transition, name='editor_survey_transition'),
    path('editor/surveys/<uuid:survey_uuid>/password/', editor_views.editor_survey_password, name='editor_survey_password'),
    path('editor/surveys/<uuid:survey_uuid>/create-draft/', editor_views.editor_create_draft, name='editor_create_draft'),
    path('editor/surveys/<uuid:survey_uuid>/publish-draft/', editor_views.editor_publish_draft, name='editor_publish_draft'),
    path('editor/surveys/<uuid:survey_uuid>/discard-draft/', editor_views.editor_discard_draft, name='editor_discard_draft'),
    path('editor/surveys/<uuid:survey_uuid>/check-compatibility/', editor_views.editor_check_compatibility, name='editor_check_compatibility'),
    # Analytics
    path('editor/surveys/<uuid:survey_uuid>/analytics/', analytics_views.analytics_dashboard, name='editor_survey_analytics'),
    path('editor/surveys/<uuid:survey_uuid>/analytics/questions/<int:question_id>/text/', analytics_views.analytics_text_answers, name='analytics_text_answers'),
    path('editor/surveys/<uuid:survey_uuid>/analytics/sessions/<int:session_id>/', analytics_views.analytics_session_detail, name='analytics_session_detail'),
    path('editor/surveys/<uuid:survey_uuid>/analytics/table/', analytics_views.analytics_table, name='analytics_table'),
    path('editor/surveys/<uuid:survey_uuid>/analytics/validation-settings/', analytics_views.analytics_validation_settings, name='analytics_validation_settings'),
    path('editor/surveys/<uuid:survey_uuid>/analytics/sessions/<int:session_id>/tags/', analytics_views.analytics_session_update_tags, name='analytics_session_update_tags'),
    path('editor/surveys/<uuid:survey_uuid>/analytics/sessions/<int:session_id>/answers/<int:question_id>/edit/', analytics_views.analytics_answer_edit, name='analytics_answer_edit'),
    path('editor/surveys/<uuid:survey_uuid>/analytics/sessions/<int:session_id>/status/', analytics_views.analytics_session_set_status, name='analytics_set_status'),
    path('editor/surveys/<uuid:survey_uuid>/analytics/sessions/<int:session_id>/trash/', analytics_views.analytics_session_trash, name='analytics_session_trash'),
    path('editor/surveys/<uuid:survey_uuid>/analytics/sessions/<int:session_id>/restore/', analytics_views.analytics_session_restore, name='analytics_session_restore'),
    path('editor/surveys/<uuid:survey_uuid>/analytics/sessions/<int:session_id>/delete/', analytics_views.analytics_session_hard_delete, name='analytics_session_hard_delete'),
    path('editor/surveys/<uuid:survey_uuid>/analytics/bulk/status/', analytics_views.analytics_bulk_set_status, name='analytics_bulk_set_status'),
    path('editor/surveys/<uuid:survey_uuid>/analytics/bulk/trash/', analytics_views.analytics_bulk_trash, name='analytics_bulk_trash'),
    path('editor/surveys/<uuid:survey_uuid>/analytics/bulk/restore/', analytics_views.analytics_bulk_restore, name='analytics_bulk_restore'),
    path('editor/surveys/<uuid:survey_uuid>/analytics/bulk/delete/', analytics_views.analytics_bulk_hard_delete, name='analytics_bulk_hard_delete'),

    # Share & tracking links
    path('editor/surveys/<uuid:survey_uuid>/share/', share_views.share_page, name='editor_survey_share'),
    path('editor/surveys/<uuid:survey_uuid>/share/<int:link_id>/delete/', share_views.share_link_delete, name='editor_survey_share_delete'),

    path('editor/surveys/<uuid:survey_uuid>/collaborators/', editor_views.editor_survey_collaborators, name='editor_survey_collaborators'),
    path('editor/surveys/<uuid:survey_uuid>/collaborators/add/', editor_views.editor_collaborator_add, name='editor_collaborator_add'),
    path('editor/surveys/<uuid:survey_uuid>/collaborators/<int:collaborator_id>/role/', editor_views.editor_collaborator_change_role, name='editor_collaborator_change_role'),
    path('editor/surveys/<uuid:survey_uuid>/collaborators/<int:collaborator_id>/remove/', editor_views.editor_collaborator_remove, name='editor_collaborator_remove'),

    path('trust/', views.trust_page, name='trust_page'),
    path('surveys/track/event/', analytics_views.analytics_track_event, name='track_event'),
    path('surveys/', views.survey_list, name='survey_list'),
    path('surveys/<str:survey_slug>/', views.survey_header, name='survey'),
    path('surveys/<str:survey_slug>/language/', views.survey_language_select, name='survey_language_select'),
    path('surveys/<str:survey_slug>/password/', views.survey_password_gate, name='survey_password_gate'),
    path('surveys/<str:survey_slug>/thanks/', views.survey_thanks, name='survey_thanks'),
    path('surveys/<str:survey_slug>/<str:section_name>/', views.survey_section, name='section'),
    path('surveys/<str:survey_slug>/download', views.download_data, name='download_data'),
    path('stories/<slug:slug>/', views.story_detail, name='story_detail'),
    path('robots.txt', views.robots_txt, name='robots_txt'),
    path('sitemap.xml', views.sitemap_xml, name='sitemap_xml'),
]
