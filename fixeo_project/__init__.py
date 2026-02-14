# This file makes the directory a Python package

from .celery import app as celery_app

__all__ = ('celery_app',)

