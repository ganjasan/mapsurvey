from django.apps import AppConfig


class SurveyConfig(AppConfig):
    name = 'survey'

    def ready(self):
        import survey.signals  # noqa: F401
