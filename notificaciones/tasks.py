from celery import shared_task
from django.conf import settings
import firebase_admin
from firebase_admin import credentials, messaging
import json
import os


_firebase_app = None


def get_firebase_app():
    global _firebase_app
    if _firebase_app is None:
        if settings.FIREBASE_CREDENTIALS:
            if os.path.isfile(settings.FIREBASE_CREDENTIALS):
                cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS)
            else:
                cred_dict = json.loads(settings.FIREBASE_CREDENTIALS)
                cred = credentials.Certificate(cred_dict)
            
            _firebase_app = firebase_admin.initialize_app(cred)
    return _firebase_app


@shared_task(name='notificaciones.notificar_usuario')
def notificar_usuario(usuario_id, titulo, mensaje, data=None):
    from usuario.models import Usuario
    from notificaciones.models import DeviceToken, Notificaciones
    
    try:
        usuario = Usuario.objects.get(id=usuario_id)
    except Usuario.DoesNotExist:
        return {'error': f'Usuario {usuario_id} no encontrado'}
    
    device_tokens = DeviceToken.objects.filter(
        usuario=usuario,
        enabled=True
    ).values_list('device_token', flat=True)
    
    if not device_tokens:
        return {'error': f'Usuario {usuario_id} no tiene device tokens'}
    
    Notificaciones.objects.create(
        usuario=usuario,
        titulo=titulo,
        descripcion=mensaje,
        deep_link=data.get('deep_link', '') if data else '',
        entity_id=data.get('entity_id', 0) if data else 0
    )
    
    try:
        get_firebase_app()
    except Exception as e:
        return {'error': f'Firebase no inicializado: {str(e)}'}
    
    tokens_enviados = 0
    tokens_fallidos = 0
    errores = []
    
    for token in device_tokens:
        try:
            notification = messaging.Notification(
                title=titulo,
                body=mensaje
            )
            
            message = messaging.Message(
                notification=notification,
                token=token,
                data=data if data else {}
            )
            
            response = messaging.send(message)
            tokens_enviados += 1
            
        except Exception as e:
            tokens_fallidos += 1
            errores.append(str(e))
            
            if 'invalid-registration-token' in str(e).lower() or 'registration-token-not-registered' in str(e).lower():
                DeviceToken.objects.filter(device_token=token).update(enabled=False)
    
    return {
        'success': True,
        'usuario_id': usuario_id,
        'tokens_enviados': tokens_enviados,
        'tokens_fallidos': tokens_fallidos,
        'errores': errores if errores else None
    }


@shared_task(name='notificaciones.notificar_usuarios_multiple')
def notificar_usuarios_multiple(usuarios_ids, titulo, mensaje, data=None):
    resultados = []
    
    for usuario_id in usuarios_ids:
        resultado = notificar_usuario.delay(usuario_id, titulo, mensaje, data)
        resultados.append({
            'usuario_id': usuario_id,
            'task_id': resultado.id
        })
    
    return {
        'success': True,
        'total_usuarios': len(usuarios_ids),
        'tareas_creadas': resultados
    }


@shared_task(name='notificaciones.limpiar_tokens_invalidos')
def limpiar_tokens_invalidos():
    from notificaciones.models import DeviceToken
    from django.utils import timezone
    from datetime import timedelta
    
    fecha_limite = timezone.now() - timedelta(days=30)
    
    tokens_eliminados = DeviceToken.objects.filter(
        enabled=False,
        updated_at__lt=fecha_limite
    ).delete()[0]
    
    return {
        'success': True,
        'tokens_eliminados': tokens_eliminados
    }
