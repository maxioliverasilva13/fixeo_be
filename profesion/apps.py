from django.apps import AppConfig


class ProfesionConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'profesion'

    def ready(self):
        import profesion.signals  # noqa: F401
