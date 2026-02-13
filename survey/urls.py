from django.urls import path

from . import views
from . import editor_views

urlpatterns = [
    path('', views.index, name='index'),
    path('editor/', views.editor, name='editor'),
    path('editor/export/<str:survey_name>/', views.export_survey, name='export_survey'),
    path('editor/import/', views.import_survey, name='import_survey'),
    path('editor/delete/<str:survey_name>/', views.delete_survey, name='delete_survey'),

    # WYSIWYG survey editor
    path('editor/surveys/new/', editor_views.editor_survey_create, name='editor_survey_create'),
    path('editor/surveys/<str:survey_name>/', editor_views.editor_survey_detail, name='editor_survey_detail'),
    path('editor/surveys/<str:survey_name>/settings/', editor_views.editor_survey_settings, name='editor_survey_settings'),
    path('editor/surveys/<str:survey_name>/sections/new/', editor_views.editor_section_create, name='editor_section_create'),
    path('editor/surveys/<str:survey_name>/sections/<int:section_id>/', editor_views.editor_section_detail, name='editor_section_detail'),
    path('editor/surveys/<str:survey_name>/sections/<int:section_id>/delete/', editor_views.editor_section_delete, name='editor_section_delete'),
    path('editor/surveys/<str:survey_name>/sections/reorder/', editor_views.editor_sections_reorder, name='editor_sections_reorder'),
    path('editor/surveys/<str:survey_name>/sections/<int:section_id>/questions/new/', editor_views.editor_question_create, name='editor_question_create'),
    path('editor/surveys/<str:survey_name>/questions/<int:question_id>/edit/', editor_views.editor_question_edit, name='editor_question_edit'),
    path('editor/surveys/<str:survey_name>/questions/<int:question_id>/delete/', editor_views.editor_question_delete, name='editor_question_delete'),
    path('editor/surveys/<str:survey_name>/questions/reorder/', editor_views.editor_questions_reorder, name='editor_questions_reorder'),
    path('editor/surveys/<str:survey_name>/questions/<int:parent_id>/subquestions/new/', editor_views.editor_subquestion_create, name='editor_subquestion_create'),
    path('editor/surveys/<str:survey_name>/sections/<int:section_id>/map/', editor_views.editor_section_map_picker, name='editor_section_map_picker'),
    path('editor/surveys/<str:survey_name>/preview/<str:section_name>/', editor_views.editor_section_preview, name='editor_section_preview'),

    path('surveys/', views.survey_list, name='survey_list'),
    path('surveys/<str:survey_name>/', views.survey_header, name='survey'),
    path('surveys/<str:survey_name>/language/', views.survey_language_select, name='survey_language_select'),
    path('surveys/<str:survey_name>/thanks/', views.survey_thanks, name='survey_thanks'),
    path('surveys/<str:survey_name>/<str:section_name>/', views.survey_section, name='section'),
    path('surveys/<str:survey_name>/download', views.download_data, name='download_data'),
    path('stories/<slug:slug>/', views.story_detail, name='story_detail'),
]