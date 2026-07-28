"""
Lógica de verificación de email pre-registro (código OTP + token de consumo).
"""

from __future__ import annotations

import secrets
import uuid
from datetime import timedelta

from django.utils import timezone
from rest_framework.exceptions import ValidationError

from notificaciones.email_service import send_verification_code_email
from usuario.models import EmailVerificationChallenge, Usuario

CODE_TTL_MINUTES = 15
RESEND_COOLDOWN_SECONDS = 60
MAX_VERIFY_ATTEMPTS = 5


def _normalize_email(email: str) -> str:
    return (email or '').strip().lower()


def _generate_code() -> str:
    return f'{secrets.randbelow(1_000_000):06d}'


def request_email_verification_code(email: str) -> dict:
    email = _normalize_email(email)
    if not email:
        raise ValidationError({'email': 'El correo es obligatorio.'})

    if Usuario.objects.filter(correo__iexact=email).exists():
        raise ValidationError({'email': 'Ya existe un usuario con este correo electrónico.'})

    latest = (
        EmailVerificationChallenge.objects
        .filter(email=email, used_at__isnull=True)
        .order_by('-created_at')
        .first()
    )
    if latest and (timezone.now() - latest.created_at).total_seconds() < RESEND_COOLDOWN_SECONDS:
        wait = RESEND_COOLDOWN_SECONDS - int((timezone.now() - latest.created_at).total_seconds())
        raise ValidationError({
            'email': f'Esperá {wait}s antes de pedir otro código.',
        })

    # Invalidar desafíos pendientes previos
    EmailVerificationChallenge.objects.filter(
        email=email,
        used_at__isnull=True,
        verified_at__isnull=True,
    ).update(expires_at=timezone.now())

    code = _generate_code()
    challenge = EmailVerificationChallenge.objects.create(
        email=email,
        code=code,
        expires_at=timezone.now() + timedelta(minutes=CODE_TTL_MINUTES),
    )

    send_result = send_verification_code_email(
        to_email=email,
        code=code,
        minutes_valid=CODE_TTL_MINUTES,
    )
    if not send_result.get('success'):
        challenge.delete()
        raise ValidationError({
            'email': 'No se pudo enviar el código. Probá de nuevo en unos minutos.',
            'detail': send_result.get('error'),
        })

    return {
        'message': 'Código enviado',
        'email': email,
        'expires_in_seconds': CODE_TTL_MINUTES * 60,
    }


def confirm_email_verification_code(email: str, code: str) -> dict:
    email = _normalize_email(email)
    code = (code or '').strip()

    if not email or not code:
        raise ValidationError('Email y código son obligatorios.')

    challenge = (
        EmailVerificationChallenge.objects
        .filter(email=email, used_at__isnull=True, verified_at__isnull=True)
        .order_by('-created_at')
        .first()
    )
    if not challenge or not challenge.is_code_valid():
        raise ValidationError({'codigo': 'Código inválido o expirado. Pedí uno nuevo.'})

    challenge.attempts += 1
    if challenge.attempts > MAX_VERIFY_ATTEMPTS:
        challenge.expires_at = timezone.now()
        challenge.save(update_fields=['attempts', 'expires_at'])
        raise ValidationError({'codigo': 'Demasiados intentos. Pedí un código nuevo.'})

    if challenge.code != code:
        challenge.save(update_fields=['attempts'])
        raise ValidationError({'codigo': 'Código incorrecto.'})

    challenge.verified_at = timezone.now()
    challenge.verification_token = uuid.uuid4()
    # Extender un poco la validez del token post-verificación (sigue el registro)
    challenge.expires_at = timezone.now() + timedelta(hours=2)
    challenge.save(update_fields=['attempts', 'verified_at', 'verification_token', 'expires_at'])

    return {
        'message': 'Correo verificado',
        'email': email,
        'email_verification_token': str(challenge.verification_token),
    }


def get_valid_email_verification_challenge(email: str, token: str) -> EmailVerificationChallenge:
    email = _normalize_email(email)
    token = (token or '').strip()
    if not email or not token:
        raise ValidationError({
            'email_verification_token': 'Tenés que verificar el correo antes de crear la cuenta.',
        })

    try:
        token_uuid = uuid.UUID(token)
    except ValueError as exc:
        raise ValidationError({'email_verification_token': 'Token de verificación inválido.'}) from exc

    challenge = EmailVerificationChallenge.objects.filter(
        email=email,
        verification_token=token_uuid,
    ).first()

    if not challenge or not challenge.is_token_consumable():
        raise ValidationError({
            'email_verification_token': 'La verificación del correo expiró o ya fue usada. Volvé a verificarlo.',
        })
    return challenge


def consume_email_verification_token(email: str, token: str) -> EmailVerificationChallenge:
    challenge = get_valid_email_verification_challenge(email, token)
    challenge.used_at = timezone.now()
    challenge.save(update_fields=['used_at'])
    return challenge
