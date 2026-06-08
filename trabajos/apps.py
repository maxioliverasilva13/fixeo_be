from django.apps import AppConfig


class TrabajosConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'trabajos'

    def ready(self):
        # Registra las shared_task de Celery al arrancar Django/worker.
        import trabajos.tasks  # noqa: F401

