from django.urls import path

from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('editor/', views.editor, name='editor'),
    path('editor/export/<str:survey_name>/', views.export_survey, name='export_survey'),
    path('editor/import/', views.import_survey, name='import_survey'),
    path('editor/delete/<str:survey_name>/', views.delete_survey, name='delete_survey'),
    path('surveys/', views.survey_list, name='survey_list'),
    path('surveys/<str:survey_name>/', views.survey_header, name='survey'),
    path('surveys/<str:survey_name>/language/', views.survey_language_select, name='survey_language_select'),
    path('surveys/<str:survey_name>/<str:section_name>/', views.survey_section, name='section'),
    path('surveys/<str:survey_name>/download', views.download_data, name='download_data'),
    path('stories/<slug:slug>/', views.story_detail, name='story_detail'),
    #path('surveys/<str:survey_name>/<str:question_code>/', views.EditAnswerForm.as_view(), name='question'),
]