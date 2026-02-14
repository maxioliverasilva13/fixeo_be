import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fixeo_project.settings')

app = Celery('fixeo_project')

app.config_from_object('django.conf:settings', namespace='CELERY')

app.autodiscover_tasks()

app.conf.beat_schedule = {
    'test-celery-cada-minuto': {
        'task': 'fixeo_project.tasks.test_celery_beat',
        'schedule': 60.0,
    },
}

app.conf.broker_connection_retry_on_startup = True

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')

@app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    from fixeo_project import tasks
    from notificaciones import tasks as notif_tasks
