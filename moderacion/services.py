from __future__ import annotations

import logging

from django.db.models import Q

from .models import ContentReport, UsuarioBlock

logger = logging.getLogger(__name__)


def users_blocked_either_way(user_a_id: int, user_b_id: int) -> bool:
    return UsuarioBlock.objects.filter(
        Q(blocker_id=user_a_id, blocked_id=user_b_id)
        | Q(blocker_id=user_b_id, blocked_id=user_a_id)
    ).exists()


def blocked_user_ids_for(user_id: int) -> set[int]:
    rows = UsuarioBlock.objects.filter(
        Q(blocker_id=user_id) | Q(blocked_id=user_id)
    ).values_list('blocker_id', 'blocked_id')
    ids: set[int] = set()
    for a, b in rows:
        if a != user_id:
            ids.add(a)
        if b != user_id:
            ids.add(b)
    return ids


def notify_moderators(report: ContentReport) -> None:
    """Log + intento de aviso por email a soporte (best-effort)."""
    logger.warning(
        'UGC report #%s type=%s content_id=%s reporter=%s reported=%s reason=%s',
        report.id,
        report.content_type,
        report.content_id,
        report.reporter_id,
        report.reported_user_id,
        report.reason,
    )
    try:
        from django.conf import settings
        from django.core.mail import send_mail

        to_addr = getattr(settings, 'SUPPORT_EMAIL', '') or 'alavueltaapp@gmail.com'
        send_mail(
            subject=f'[ALaVuelta] Nuevo reporte UGC #{report.id}',
            message=(
                f'Tipo: {report.content_type}\n'
                f'Content ID: {report.content_id}\n'
                f'Reporter: {report.reporter_id}\n'
                f'Reported: {report.reported_user_id}\n'
                f'Reason: {report.reason}\n'
                f'Details: {report.details}\n'
                f'Actuar dentro de 24 horas (Guideline 1.2).\n'
            ),
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', None),
            recipient_list=[str(to_addr)],
            fail_silently=True,
        )
    except Exception:
        logger.exception('No se pudo notificar reporte UGC #%s', report.id)
