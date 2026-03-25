"""
Inicialización idempotente de Firebase Admin (Django web, Celery workers, tareas concurrentes).
Evita llamar initialize_app() dos veces en el mismo proceso.
"""
from __future__ import annotations

import json
import os
import threading

import firebase_admin
from firebase_admin import credentials

_lock = threading.Lock()


def ensure_firebase_app(credentials_source: str | None = None):
    """
    Devuelve la app [DEFAULT] de Firebase Admin.

    Si credentials_source es None, lee FIREBASE_CREDENTIALS desde django.conf.settings
    (solo después de que Django cargó settings).
    """
    try:
        return firebase_admin.get_app()
    except ValueError:
        pass

    with _lock:
        try:
            return firebase_admin.get_app()
        except ValueError:
            pass

        if credentials_source is None:
            from django.conf import settings as dj_settings

            credentials_source = getattr(dj_settings, 'FIREBASE_CREDENTIALS', None)

        if not credentials_source:
            return None

        if os.path.isfile(str(credentials_source)):
            cred = credentials.Certificate(credentials_source)
        else:
            cred_dict = json.loads(credentials_source)
            cred = credentials.Certificate(cred_dict)

        try:
            return firebase_admin.initialize_app(cred)
        except ValueError as e:
            if 'already exists' in str(e).lower():
                return firebase_admin.get_app()
            raise
