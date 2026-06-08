"""Mensajes de chat vinculados a órdenes (metadata + WebSocket)."""
from django.db.models import Q
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from mensajeria.models import Chat, Mensajes
from .serializers import OrdenMensajeResumenSerializer


def _get_or_create_chat(usuario, admin):
    chat = Chat.objects.filter(
        Q(sender=usuario, receiver=admin) | Q(sender=admin, receiver=usuario)
    ).first()
    if not chat:
        chat = Chat.objects.create(sender=admin, receiver=usuario)
    return chat


def _orden_metadata_snapshot(orden, tipo):
    return {
        'orden_id': orden.id,
        'tipo': tipo,
        'numero_orden': orden.numero_orden,
        'status': orden.status,
    }


def _orden_data_for_mensaje(orden, metadata=None):
    data = OrdenMensajeResumenSerializer(orden).data
    meta = metadata or {}
    if meta.get('status'):
        data['status'] = meta['status']
    return data


def _ws_payload(chat, mensaje, orden, sender_user):
    orden_data = _orden_data_for_mensaje(orden, mensaje.metadata)
    if chat.sender_id == sender_user.id:
        receiver_user = chat.receiver
    else:
        receiver_user = chat.sender
    return {
        'type': 'chat_message',
        'message': mensaje.texto,
        'user_id': sender_user.id,
        'leido': False,
        'chat_id': chat.id,
        'orden': orden_data,
        'chat': {
            'id': chat.id,
            'sender_id': sender_user.id,
            'sender_nombre': f'{sender_user.nombre} {sender_user.apellido}',
            'receiver_id': receiver_user.id,
            'receiver_nombre': f'{receiver_user.nombre} {receiver_user.apellido}',
            'trabajo_id': chat.trabajo_id,
            'ultimo_mensaje_at': mensaje.created_at.isoformat(),
        },
    }


def enviar_mensaje_orden_chat(orden, *, texto, sender, receiver, tipo='orden'):
    """Crea mensaje de chat con referencia a la orden y notifica por WebSocket."""
    chat = _get_or_create_chat(orden.usuario, orden.empresa.admin_id)
    mensaje = Mensajes.objects.create(
        texto=texto,
        sender=sender,
        chat=chat,
        metadata=_orden_metadata_snapshot(orden, tipo),
    )
    channel_layer = get_channel_layer()
    room_name = f'usuario_channel_{receiver.id}'
    async_to_sync(channel_layer.group_send)(
        f'chat_{room_name}',
        _ws_payload(chat, mensaje, orden, sender),
    )
    return mensaje
