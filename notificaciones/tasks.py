import logging
from celery import shared_task
from firebase_admin import messaging

from fixeo_project.firebase_init import ensure_firebase_app
from notificaciones.email_service import send_notification_email

logger = logging.getLogger(__name__)


def get_firebase_app():
    return ensure_firebase_app()


def _fcm_token_invalido(error: Exception) -> bool:
    """True si Firebase indica que el token ya no sirve para push."""
    msg = str(error).lower()
    return (
        'invalid-registration-token' in msg
        or 'registration-token-not-registered' in msg
        or 'requested entity was not found' in msg
        or 'not found' in msg and 'entity' in msg
    )


def _enviar_push(usuario, titulo, mensaje, data=None) -> dict:
    from notificaciones.models import DeviceToken

    device_tokens = list(
        DeviceToken.objects.filter(
            usuario=usuario,
            enabled=True,
        ).values_list('device_token', flat=True)
    )

    if not device_tokens:
        return {'push_skipped': True, 'reason': 'no_tokens'}

    try:
        app = get_firebase_app()
        if app is None:
            return {'push_skipped': True, 'error': 'Firebase no configurado (FIREBASE_CREDENTIALS vacío)'}
    except Exception as e:
        return {'push_skipped': True, 'error': f'Firebase no inicializado: {str(e)}'}

    firebase_data = {}
    if data:
        for key, value in data.items():
            firebase_data[key] = str(value)

    tokens_enviados = 0
    tokens_fallidos = 0
    errores = []

    for token in device_tokens:
        try:
            notification = messaging.Notification(
                title=titulo,
                body=mensaje,
            )
            message = messaging.Message(
                notification=notification,
                token=token,
                data=firebase_data,
            )
            messaging.send(message)
            tokens_enviados += 1
        except Exception as e:
            tokens_fallidos += 1
            errores.append(str(e))
            if _fcm_token_invalido(e):
                disabled = DeviceToken.objects.filter(device_token=token).update(enabled=False)
                if disabled:
                    logger.info(
                        'Token FCM inválido desactivado (usuario=%s): %s',
                        usuario.id,
                        str(e),
                    )

    return {
        'tokens_enviados': tokens_enviados,
        'tokens_fallidos': tokens_fallidos,
        'errores': errores if errores else None,
    }


@shared_task(name='notificaciones.notificar_usuario')
def notificar_usuario(usuario_id, titulo, mensaje, data=None):
    from usuario.models import Usuario
    from notificaciones.models import Notificaciones

    try:
        usuario = Usuario.objects.get(id=usuario_id)
    except Usuario.DoesNotExist:
        return {'error': f'Usuario {usuario_id} no encontrado'}

    # Siempre se guarda en el inbox in-app.
    Notificaciones.objects.create(
        usuario=usuario,
        titulo=titulo,
        descripcion=mensaje,
        deep_link=data.get('deep_link', '') if data else '',
        entity_id=data.get('entity_id', 0) if data else 0,
    )

    result = {
        'success': True,
        'usuario_id': usuario_id,
        'push': None,
        'email': None,
    }

    if getattr(usuario, 'recibir_notificaciones', True):
        result['push'] = _enviar_push(usuario, titulo, mensaje, data)
    else:
        result['push'] = {'push_skipped': True, 'reason': 'recibir_notificaciones=False'}

    if getattr(usuario, 'recibir_correos', True):
        nombre = f'{usuario.nombre or ""} {usuario.apellido or ""}'.strip()
        result['email'] = send_notification_email(
            to_email=usuario.correo,
            titulo=titulo,
            mensaje=mensaje,
            data=data,
            usuario_nombre=nombre,
        )
    else:
        result['email'] = {'email_skipped': True, 'reason': 'recibir_correos=False'}

    return result


WELCOME_PROFESIONAL_CHAT_PROMO = (
    '¡Hola {nombre}! 👋 Gracias por sumarte a ALaVuelta.\n\n'
    'Por ser de los primeros en registrarte, durante los primeros 3 meses '
    'vas a tener una página web propia para tu negocio.\n\n'
    'Podés configurarla desde Perfil → Landing page. '
    'Si no la ves en tu perfil, escribinos desde Mensajes '
    '(chat con el administrador) y te habilitamos el acceso.\n\n'
    'Conocé más en {web_url}\n\n'
    '¡Bienvenido/a! Estamos para ayudarte en lo que necesites.'
)

WELCOME_PROFESIONAL_CHAT_STANDARD = (
    '¡Hola {nombre}! 👋 Gracias por sumarte a ALaVuelta.\n\n'
    'Ya podés empezar a recibir clientes, gestionar pedidos y hacer crecer '
    'tu negocio desde la app.\n\n'
    'Conocé más sobre ALaVuelta en {web_url}\n\n'
    '¡Bienvenido/a! Cualquier duda, escribinos desde Mensajes.'
)


@shared_task(
    bind=True,
    name='notificaciones.enviar_bienvenida_profesional',
    max_retries=5,
    default_retry_delay=5,
    ignore_result=True,
)
def enviar_bienvenida_profesional(self, usuario_id):
    """
    Da la bienvenida a un profesional recién registrado:
    - Crea (o reutiliza) el chat de soporte con el admin y envía un mensaje.
    - Envía el email de bienvenida (promo landing o estándar según empresas activas).
    """
    from django.db.models import Q
    from channels.layers import get_channel_layer
    from asgiref.sync import async_to_sync

    from usuario.models import Usuario
    from mensajeria.models import Chat, Mensajes
    from notificaciones.email_service import send_welcome_professional_email
    from empresas.promo import (
        WELCOME_WEB_URL,
        count_empresas_activas,
        welcome_usa_promo_landing,
    )

    try:
        usuario = Usuario.objects.get(id=usuario_id)
    except Usuario.DoesNotExist as exc:
        # El commit de la cuenta puede no ser visible aún para el worker
        # (transacción en curso / latencia de replica). Reintentamos.
        if self.request.retries < self.max_retries:
            logger.info(
                'Bienvenida: usuario %s aún no visible, reintentando (%s/%s)',
                usuario_id, self.request.retries + 1, self.max_retries,
            )
            raise self.retry(exc=exc)
        return {'error': f'Usuario {usuario_id} no encontrado'}

    empresas_activas = count_empresas_activas()
    # Alinear el mensaje con el flag seteado al crear la empresa (antes del insert).
    empresa = usuario.empresas_administradas.first()
    if empresa is not None:
        usa_promo = bool(empresa.tiene_landing_page)
    else:
        usa_promo = welcome_usa_promo_landing(empresas_activas)
    result = {
        'success': True,
        'usuario_id': usuario_id,
        'promo_landing': usa_promo,
        'empresas_activas': empresas_activas,
        'chat': None,
        'email': None,
    }

    # --- Mensaje de chat desde la cuenta admin (mismo patrón que el chat de soporte) ---
    admin = Usuario.objects.filter(rol__nombre='admin').order_by('id').first()
    if not admin:
        result['chat'] = {'skipped': True, 'reason': 'no_admin'}
    elif admin.id == usuario.id:
        result['chat'] = {'skipped': True, 'reason': 'usuario_es_admin'}
    else:
        chat = Chat.objects.filter(
            Q(sender=admin, receiver=usuario) | Q(sender=usuario, receiver=admin)
        ).first()
        if not chat:
            chat = Chat.objects.create(sender=admin, receiver=usuario)

        plantilla = WELCOME_PROFESIONAL_CHAT_PROMO if usa_promo else WELCOME_PROFESIONAL_CHAT_STANDARD
        texto = plantilla.format(
            nombre=usuario.nombre or '',
            web_url=WELCOME_WEB_URL,
        )
        mensaje = Mensajes.objects.create(
            texto=texto,
            sender=admin,
            chat=chat,
            tipo=Mensajes.TipoMensaje.TEXTO,
        )
        chat.ultimo_mensaje_at = mensaje.created_at
        chat.save()

        try:
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(f'user_{usuario.id}', {
                'type': 'chat_message',
                'message': mensaje.texto,
                'mensaje_id': mensaje.mensaje_id,
                'user_id': admin.id,
                'created_at': mensaje.created_at.isoformat(),
                'chat_id': chat.id,
                'leido': False,
                'tipo': mensaje.tipo,
                'metadata': mensaje.metadata,
                'recurso': None,
            })
        except Exception as e:
            logger.warning('Bienvenida: fallo al emitir por websocket (usuario=%s): %s', usuario_id, e)

        result['chat'] = {'chat_id': chat.id, 'mensaje_id': mensaje.mensaje_id}

    # --- Email de bienvenida ---
    if getattr(usuario, 'recibir_correos', True):
        nombre = f'{usuario.nombre or ""} {usuario.apellido or ""}'.strip()
        result['email'] = send_welcome_professional_email(
            to_email=usuario.correo,
            usuario_nombre=nombre,
            promo_landing=usa_promo,
            web_url=WELCOME_WEB_URL,
        )
    else:
        result['email'] = {'email_skipped': True, 'reason': 'recibir_correos=False'}

    return result


# Compat: por si algún import antiguo referencia la constante anterior
WELCOME_PROFESIONAL_CHAT = WELCOME_PROFESIONAL_CHAT_PROMO
WELCOME_WEB_URL = 'https://alavueltaapp.pro'
EMPRESAS_ACTIVAS_PROMO_THRESHOLD = 100


@shared_task(name='notificaciones.notificar_usuarios_multiple')
def notificar_usuarios_multiple(usuarios_ids, titulo, mensaje, data=None):
    resultados = []

    firebase_data = {}
    if data:
        for key, value in data.items():
            firebase_data[key] = str(value)

    for usuario_id in usuarios_ids:
        resultado = notificar_usuario.delay(usuario_id, titulo, mensaje, firebase_data)
        resultados.append({
            'usuario_id': usuario_id,
            'task_id': resultado.id,
        })

    return {
        'success': True,
        'total_usuarios': len(usuarios_ids),
        'tareas_creadas': resultados,
    }


@shared_task(name='notificaciones.limpiar_tokens_invalidos')
def limpiar_tokens_invalidos():
    from notificaciones.models import DeviceToken
    from django.utils import timezone
    from datetime import timedelta

    fecha_limite = timezone.now() - timedelta(days=30)

    tokens_eliminados = DeviceToken.objects.filter(
        enabled=False,
        updated_at__lt=fecha_limite,
    ).delete()[0]

    return {
        'success': True,
        'tokens_eliminados': tokens_eliminados,
    }
