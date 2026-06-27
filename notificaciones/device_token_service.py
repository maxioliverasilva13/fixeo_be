from .models import DeviceToken


def activate_device_token_for_user(usuario, device_token: str, device_name: str = 'Fixeo App') -> tuple[DeviceToken, bool]:
    """
    Asocia el token FCM al usuario activo y lo desactiva para cualquier otro usuario
    en el mismo dispositivo (mismo device_token).
    """
    DeviceToken.objects.filter(device_token=device_token).exclude(usuario=usuario).update(enabled=False)

    token_obj, created = DeviceToken.objects.update_or_create(
        usuario=usuario,
        device_token=device_token,
        defaults={
            'device_name': device_name,
            'enabled': True,
        },
    )
    return token_obj, created


def deactivate_device_token_for_user(usuario, device_token: str) -> int:
    """Desactiva el token FCM de este usuario en el dispositivo actual (logout)."""
    return DeviceToken.objects.filter(
        usuario=usuario,
        device_token=device_token,
    ).update(enabled=False)
