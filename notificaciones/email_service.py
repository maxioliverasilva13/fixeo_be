"""
Servicio reutilizable de emails HTML para ALaVuelta / Fixeo.

Layout único (header con logo + card + CTA + footer). El cuerpo cambia
según `tipo` (orden, trabajo, oferta, calificación, etc.).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Optional
from urllib.parse import urljoin

import resend
from django.conf import settings

logger = logging.getLogger(__name__)

# Brand (mismo look & feel que fixeo_FE)
PRIMARY = '#8972FD'
PRIMARY_LIGHT = '#AFA0FF'
PRIMARY_LIGHTER = '#EFEAFF'
BACKGROUND = '#F7F7FB'
BORDER = '#E4E5F1'
TEXT = '#0F0F0F'
MUTED = '#6E6E80'
WHITE = '#FFFFFF'


@dataclass
class EmailContent:
    subject: str
    badge: str
    headline: str
    body_html: str
    cta_label: str = 'Ver en la app'
    cta_url: str = ''


def _frontend_url(path: str = '') -> str:
    base = (getattr(settings, 'FRONTEND_URL', None) or 'http://localhost:8081').rstrip('/') + '/'
    if not path:
        return base.rstrip('/')
    return urljoin(base, path.lstrip('/'))


def _logo_url() -> str:
    custom = getattr(settings, 'EMAIL_LOGO_URL', '') or ''
    if custom:
        return custom
    return _frontend_url('app-logo.png')


def _from_address() -> str:
    return getattr(settings, 'EMAIL_FROM', None) or 'onboarding@resend.dev'


def _escape(text: str) -> str:
    return (
        (text or '')
        .replace('&', '&amp;')
        .replace('<', '&lt;')
        .replace('>', '&gt;')
        .replace('"', '&quot;')
    )


def _tipo_meta(tipo: str) -> tuple[str, str]:
    """(badge_label, accent_color) por tipo de notificación."""
    mapping = {
        'nueva_orden': ('Nueva orden', '#8972FD'),
        'trabajo_aceptado': ('Trabajo aceptado', '#1F8D63'),
        'trabajo_rechazado': ('Trabajo rechazado', '#D64545'),
        'trabajo_creado': ('Nuevo trabajo', '#8972FD'),
        'trabajo_finalizado': ('Trabajo finalizado', '#6E57D8'),
        'calificacion_pendiente': ('Calificá tu experiencia', '#F59E0B'),
        'calificacion_pendiente_profesional': ('Calificá al cliente', '#F59E0B'),
        'nuevo_trabajo_urgente': ('Trabajo urgente', '#EF4444'),
        'nueva_oferta': ('Nueva oferta', '#8972FD'),
        'oferta_aceptada': ('Oferta aceptada', '#1F8D63'),
        'oferta_rechazada': ('Oferta rechazada', '#D64545'),
        'trabajo_urgente_cancelado': ('Trabajo cancelado', '#D64545'),
        'mensaje': ('Nuevo mensaje', '#8972FD'),
    }
    return mapping.get(tipo or '', ('Notificación', PRIMARY))


def build_notification_content(
    *,
    titulo: str,
    mensaje: str,
    data: Optional[dict[str, Any]] = None,
    usuario_nombre: str = '',
) -> EmailContent:
    data = data or {}
    tipo = str(data.get('tipo') or '')
    badge, _accent = _tipo_meta(tipo)
    deep_link = str(data.get('deep_link') or '')
    cta_url = _frontend_url(deep_link) if deep_link else _frontend_url()

    greeting = f'Hola {_escape(usuario_nombre)},' if usuario_nombre else 'Hola,'
    detalle_extra = ''

    if tipo == 'nueva_orden':
        detalle_extra = (
            '<p style="margin:0 0 12px;font-size:14px;color:#6E6E80;line-height:1.6;">'
            'Tenés una nueva orden pendiente. Revisala y prepará el pedido o el servicio.'
            '</p>'
        )
    elif tipo in ('trabajo_aceptado', 'oferta_aceptada'):
        detalle_extra = (
            '<p style="margin:0 0 12px;font-size:14px;color:#6E6E80;line-height:1.6;">'
            'Todo listo para continuar. Abrí la app para ver los detalles y coordinar.'
            '</p>'
        )
    elif tipo in ('trabajo_rechazado', 'oferta_rechazada', 'trabajo_urgente_cancelado'):
        detalle_extra = (
            '<p style="margin:0 0 12px;font-size:14px;color:#6E6E80;line-height:1.6;">'
            'Podés revisar el motivo o buscar otras opciones desde la app.'
            '</p>'
        )
    elif tipo in ('calificacion_pendiente', 'calificacion_pendiente_profesional'):
        detalle_extra = (
            '<p style="margin:0 0 12px;font-size:14px;color:#6E6E80;line-height:1.6;">'
            'Tu opinión ayuda a mejorar la comunidad. Solo te toma un momento.'
            '</p>'
        )
    elif tipo == 'nuevo_trabajo_urgente':
        detalle_extra = (
            '<p style="margin:0 0 12px;font-size:14px;color:#6E6E80;line-height:1.6;">'
            'Hay un trabajo urgente cerca tuyo. Respondé rápido si podés tomarlo.'
            '</p>'
        )
    elif tipo == 'nueva_oferta':
        detalle_extra = (
            '<p style="margin:0 0 12px;font-size:14px;color:#6E6E80;line-height:1.6;">'
            'Recibiste una nueva oferta. Comparala y aceptá la que más te convenga.'
            '</p>'
        )

    body_html = f"""
      <p style="margin:0 0 8px;font-size:15px;color:{TEXT};line-height:1.5;">{greeting}</p>
      <p style="margin:0 0 16px;font-size:15px;color:{TEXT};font-weight:600;line-height:1.5;">
        {_escape(titulo)}
      </p>
      <div style="background:{PRIMARY_LIGHTER};border:1px solid {BORDER};border-radius:14px;padding:16px 18px;margin:0 0 16px;">
        <p style="margin:0;font-size:14px;color:{MUTED};line-height:1.65;">{_escape(mensaje)}</p>
      </div>
      {detalle_extra}
    """

    return EmailContent(
        subject=titulo or 'Notificación de ALaVuelta',
        badge=badge,
        headline=titulo or 'Tenés una novedad',
        body_html=body_html,
        cta_label='Abrir en ALaVuelta',
        cta_url=cta_url,
    )


def render_email_html(
    content: EmailContent,
    *,
    footer_text: str = (
        'Recibiste este correo porque tenés activadas las notificaciones por email en ALaVuelta. '
        'Podés cambiarlo desde Perfil → Notificaciones.'
    ),
) -> str:
    logo = _logo_url()
    cta = ''
    if content.cta_url:
        cta = f"""
          <a href="{_escape(content.cta_url)}"
             style="display:inline-block;padding:14px 28px;background:linear-gradient(135deg,{PRIMARY},{PRIMARY_LIGHT});
                    color:#fff;font-size:15px;font-weight:700;text-align:center;border-radius:14px;
                    text-decoration:none;box-shadow:0 4px 20px rgba(137,114,253,0.35);">
            {_escape(content.cta_label)}
          </a>
        """

    return f"""
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{_escape(content.subject)}</title>
</head>
<body style="margin:0;padding:0;background:{BACKGROUND};font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{BACKGROUND};padding:32px 16px;">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:520px;background:{WHITE};border-radius:20px;border:1px solid {BORDER};overflow:hidden;">
          <tr>
            <td style="background:linear-gradient(135deg,{PRIMARY},{PRIMARY_LIGHT});padding:28px 24px;text-align:center;">
              <img src="{_escape(logo)}" alt="ALaVuelta" width="56" height="56"
                   style="display:inline-block;border-radius:14px;background:#fff;object-fit:cover;" />
              <p style="margin:14px 0 0;font-size:18px;font-weight:800;color:#fff;letter-spacing:0.02em;">ALaVuelta</p>
            </td>
          </tr>
          <tr>
            <td style="padding:28px 24px 8px;">
              <span style="display:inline-block;padding:6px 12px;border-radius:999px;background:{PRIMARY_LIGHTER};
                           color:{PRIMARY};font-size:11px;font-weight:700;letter-spacing:0.04em;text-transform:uppercase;">
                {_escape(content.badge)}
              </span>
              <h1 style="margin:14px 0 0;font-size:22px;font-weight:800;color:{TEXT};line-height:1.25;">
                {_escape(content.headline)}
              </h1>
            </td>
          </tr>
          <tr>
            <td style="padding:8px 24px 24px;">
              {content.body_html}
              <div style="text-align:center;margin-top:8px;">{cta}</div>
            </td>
          </tr>
          <tr>
            <td style="padding:18px 24px 24px;border-top:1px solid {BORDER};">
              <p style="margin:0;font-size:12px;color:{MUTED};line-height:1.5;text-align:center;">
                {_escape(footer_text)}
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""


def _resolve_recipient(to_email: str) -> tuple[str, Optional[str]]:
    sandbox_to = (getattr(settings, 'EMAIL_SANDBOX_TO', None) or '').strip()
    if sandbox_to and to_email.lower() != sandbox_to.lower():
        return sandbox_to, to_email
    return to_email, None


def send_html_email(*, to_email: str, subject: str, html: str) -> dict[str, Any]:
    api_key = getattr(settings, 'RESEND_API_KEY', None) or ''
    if not api_key:
        logger.warning('Email omitido: RESEND_API_KEY vacío')
        return {'success': False, 'error': 'RESEND_API_KEY vacío'}
    if not to_email:
        return {'success': False, 'error': 'sin correo'}

    destination, original_to = _resolve_recipient(to_email)
    final_subject = subject
    if original_to:
        final_subject = f'[sandbox → {original_to}] {subject}'

    try:
        resend.api_key = api_key
        result = resend.Emails.send({
            'from': _from_address(),
            'to': [destination],
            'subject': final_subject,
            'html': html,
        })
        logger.info('📧 Email enviado a %s', destination)
        return {'success': True, 'result': result, 'to': destination, 'original_to': original_to}
    except Exception as exc:
        logger.exception('Error enviando email a %s', to_email)
        return {'success': False, 'error': str(exc)}


def send_verification_code_email(*, to_email: str, code: str, minutes_valid: int = 15) -> dict[str, Any]:
    content = EmailContent(
        subject=f'Tu código de verificación: {code}',
        badge='Verificación',
        headline='Confirmá tu correo',
        body_html=f"""
          <p style="margin:0 0 12px;font-size:15px;color:{TEXT};line-height:1.5;">
            Usá este código para continuar con el registro en ALaVuelta:
          </p>
          <div style="text-align:center;margin:20px 0;">
            <div style="display:inline-block;padding:16px 28px;border-radius:16px;background:{PRIMARY_LIGHTER};
                        border:1px solid {BORDER};letter-spacing:0.35em;font-size:28px;font-weight:800;color:{PRIMARY};">
              {_escape(code)}
            </div>
          </div>
          <p style="margin:0;font-size:13px;color:{MUTED};line-height:1.6;text-align:center;">
            El código vence en {minutes_valid} minutos. Si no pediste crear una cuenta, ignorá este correo.
          </p>
        """,
        cta_label='',
        cta_url='',
    )
    html = render_email_html(
        content,
        footer_text='Este código solo se usa para verificar tu correo al registrarte en ALaVuelta.',
    )
    return send_html_email(to_email=to_email, subject=content.subject, html=html)


def send_notification_email(
    *,
    to_email: str,
    titulo: str,
    mensaje: str,
    data: Optional[dict[str, Any]] = None,
    usuario_nombre: str = '',
) -> dict[str, Any]:
    """
    Envía un email de notificación con el layout brand.
    Retorna dict con success/error (no lanza, para no romper el flow de push).
    """
    if not to_email:
        return {'success': False, 'error': 'sin correo'}

    content = build_notification_content(
        titulo=titulo,
        mensaje=mensaje,
        data=data,
        usuario_nombre=usuario_nombre,
    )
    html = render_email_html(content)
    return send_html_email(to_email=to_email, subject=content.subject, html=html)
