"""
Estadísticas globales para el panel de administración (superadmin).
Devuelve métricas agregadas de todas las entidades del sistema.
"""
from calendar import monthrange
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.db.models import Count, Sum, Avg, Q, F
from django.db.models.functions import TruncDate, TruncMonth
from django.utils import timezone

from usuario.models import Usuario
from suscripciones.models import Subscripcion, Plan
from empresas.models import Empresa
from trabajos.models import Trabajo, Calificacion
from carritos.models import Orden, OrdenItem
from pagos.models import Pago
from survey.models import SurveyResponse
from mensajeria.models import Chat, Mensajes


def _decimal_str(value) -> str:
    if value is None:
        return '0.00'
    return f'{Decimal(value):.2f}'


def _parse_period(request):
    """Parsea período desde query params (year/month)."""
    now = timezone.localtime(timezone.now())
    try:
        year = int(request.query_params.get('year', now.year))
        month = int(request.query_params.get('month', now.month))
    except (TypeError, ValueError):
        year, month = now.year, now.month
    month = max(1, min(12, month))
    year = max(2000, min(2100, year))
    _, last_day = monthrange(year, month)
    start = timezone.make_aware(datetime(year, month, 1, 0, 0, 0))
    if month == 12:
        end = timezone.make_aware(datetime(year + 1, 1, 1, 0, 0, 0))
    else:
        end = timezone.make_aware(datetime(year, month + 1, 1, 0, 0, 0))
    return year, month, last_day, start, end


def estadisticas_usuarios(start, end):
    """Estadísticas de usuarios."""
    total_usuarios = Usuario.objects.count()
    nuevos_periodo = Usuario.objects.filter(created_at__gte=start, created_at__lt=end).count()

    # Por rol
    usuarios_por_rol = list(
        Usuario.objects.values('rol__nombre')
        .annotate(cantidad=Count('id'))
        .order_by('-cantidad')
    )

    # Owners de empresa
    owners_empresa = Usuario.objects.filter(is_owner_empresa=True).count()

    # Profesionales (tienen trabajo asignado o servicios)
    profesionales = Usuario.objects.filter(
        Q(trabajos_asignados__isnull=False) | Q(servicios__isnull=False)
    ).distinct().count()

    # Usuarios con suscripción activa
    ahora = timezone.now()
    usuarios_con_sub = Subscripcion.objects.filter(
        cancelada=False,
        expiracion__gt=ahora,
    ).values('user_id').distinct().count()

    # Usuarios por mes (últimos 12 meses)
    hace_12_meses = ahora - timedelta(days=365)
    usuarios_por_mes = list(
        Usuario.objects.filter(created_at__gte=hace_12_meses)
        .annotate(mes=TruncMonth('created_at'))
        .values('mes')
        .annotate(cantidad=Count('id'))
        .order_by('mes')
    )

    return {
        'total_usuarios': total_usuarios,
        'nuevos_en_periodo': nuevos_periodo,
        'usuarios_por_rol': [
            {'rol': r['rol__nombre'] or 'Sin rol', 'cantidad': r['cantidad']}
            for r in usuarios_por_rol
        ],
        'owners_empresa': owners_empresa,
        'profesionales_activos': profesionales,
        'usuarios_con_suscripcion_activa': usuarios_con_sub,
        'usuarios_por_mes': [
            {
                'mes': r['mes'].strftime('%Y-%m') if r['mes'] else None,
                'cantidad': r['cantidad']
            }
            for r in usuarios_por_mes
        ],
    }


def estadisticas_suscripciones(start, end):
    """Estadísticas de suscripciones."""
    ahora = timezone.now()

    total_subs = Subscripcion.objects.count()
    subs_activas = Subscripcion.objects.filter(cancelada=False, expiracion__gt=ahora).count()
    subs_canceladas = Subscripcion.objects.filter(cancelada=True).count()
    subs_expiradas = Subscripcion.objects.filter(cancelada=False, expiracion__lte=ahora).count()

    # Por plan
    subs_por_plan = list(
        Subscripcion.objects.values('plan_id__nombre', 'plan_id__precio')
        .annotate(
            cantidad=Count('id'),
            activas=Count('id', filter=Q(cancelada=False, expiracion__gt=ahora)),
        )
        .order_by('-cantidad')
    )

    # Por status
    subs_por_status = list(
        Subscripcion.objects.values('status')
        .annotate(cantidad=Count('id'))
        .order_by('-cantidad')
    )

    # Por fuente (manual, google_play, app_store)
    subs_por_fuente = list(
        Subscripcion.objects.values('source')
        .annotate(cantidad=Count('id'))
        .order_by('-cantidad')
    )

    # Nuevas en período
    nuevas_periodo = Subscripcion.objects.filter(created_at__gte=start, created_at__lt=end).count()

    # Renovaciones/cancelaciones en período
    canceladas_periodo = Subscripcion.objects.filter(
        cancelada=True, updated_at__gte=start, updated_at__lt=end
    ).count()

    # Jobs restantes promedio
    jobs_promedio = Subscripcion.objects.filter(
        cancelada=False, expiracion__gt=ahora
    ).aggregate(promedio=Avg('jobs_restantes'))['promedio'] or 0

    # Subs por mes (últimos 12 meses)
    hace_12_meses = ahora - timedelta(days=365)
    subs_por_mes = list(
        Subscripcion.objects.filter(created_at__gte=hace_12_meses)
        .annotate(mes=TruncMonth('created_at'))
        .values('mes')
        .annotate(cantidad=Count('id'))
        .order_by('mes')
    )

    return {
        'total_suscripciones': total_subs,
        'activas': subs_activas,
        'canceladas': subs_canceladas,
        'expiradas': subs_expiradas,
        'nuevas_en_periodo': nuevas_periodo,
        'canceladas_en_periodo': canceladas_periodo,
        'jobs_restantes_promedio': round(jobs_promedio, 2),
        'por_plan': [
            {
                'plan': s['plan_id__nombre'],
                'precio': _decimal_str(s['plan_id__precio']),
                'total': s['cantidad'],
                'activas': s['activas'],
            }
            for s in subs_por_plan
        ],
        'por_status': [
            {'status': s['status'], 'cantidad': s['cantidad']}
            for s in subs_por_status
        ],
        'por_fuente': [
            {'fuente': s['source'], 'cantidad': s['cantidad']}
            for s in subs_por_fuente
        ],
        'suscripciones_por_mes': [
            {
                'mes': s['mes'].strftime('%Y-%m') if s['mes'] else None,
                'cantidad': s['cantidad']
            }
            for s in subs_por_mes
        ],
    }


def estadisticas_planes():
    """Estadísticas de planes disponibles."""
    planes = Plan.objects.all().order_by('precio')
    return {
        'total_planes': planes.count(),
        'planes_activos': planes.filter(activo=True).count(),
        'planes': [
            {
                'id': p.id,
                'nombre': p.nombre,
                'precio': _decimal_str(p.precio),
                'duracion_dias': p.duracion.days if p.duracion else 0,
                'cantidad_personas': p.cantidad_personas,
                'cantidad_jobs': p.cantidad_jobs,
                'activo': p.activo,
                'total_subscripciones': p.subscripciones.count(),
                'subscripciones_activas': p.subscripciones.filter(
                    cancelada=False, expiracion__gt=timezone.now()
                ).count(),
            }
            for p in planes
        ],
    }


def estadisticas_empresas(start, end):
    """Estadísticas de empresas."""
    total_empresas = Empresa.objects.count()
    nuevas_periodo = Empresa.objects.filter(created_at__gte=start, created_at__lt=end).count()

    # Por país
    empresas_por_pais = list(
        Empresa.objects.values('pais')
        .annotate(cantidad=Count('id'))
        .order_by('-cantidad')
    )

    # Por tipo (vende productos, servicios, ambos)
    solo_productos = Empresa.objects.filter(vende_productos=True, vende_servicios=False).count()
    solo_servicios = Empresa.objects.filter(vende_productos=False, vende_servicios=True).count()
    ambos = Empresa.objects.filter(vende_productos=True, vende_servicios=True).count()

    # Con MP vinculado
    con_mp = Empresa.objects.filter(is_mercadopago_vinculado=True).count()

    # Unipersonales
    unipersonales = Empresa.objects.filter(unipersonal=True).count()

    return {
        'total_empresas': total_empresas,
        'nuevas_en_periodo': nuevas_periodo,
        'por_pais': [
            {'pais': e['pais'], 'cantidad': e['cantidad']}
            for e in empresas_por_pais
        ],
        'solo_productos': solo_productos,
        'solo_servicios': solo_servicios,
        'ambos': ambos,
        'con_mercadopago': con_mp,
        'unipersonales': unipersonales,
    }


def estadisticas_trabajos(start, end):
    """Estadísticas de trabajos/servicios."""
    total_trabajos = Trabajo.objects.count()
    trabajos_periodo = Trabajo.objects.filter(created_at__gte=start, created_at__lt=end)

    # Por status
    por_status = list(
        Trabajo.objects.values('status')
        .annotate(cantidad=Count('id'))
        .order_by('-cantidad')
    )

    # Urgentes
    urgentes = Trabajo.objects.filter(esUrgente=True).count()
    urgentes_periodo = trabajos_periodo.filter(esUrgente=True).count()

    # Ingresos por trabajos finalizados
    ingresos = Trabajo.objects.filter(
        status='finalizado',
        precio_final__isnull=False,
        created_at__gte=start,
        created_at__lt=end,
    ).aggregate(total=Sum('precio_final'))['total'] or Decimal('0')

    # Calificaciones promedio
    avg_rating = Calificacion.objects.aggregate(promedio=Avg('rating'))['promedio'] or 0
    total_calificaciones = Calificacion.objects.count()

    # Trabajos por método de pago
    por_metodo_pago = list(
        Trabajo.objects.exclude(metodo_pago__isnull=True)
        .values('metodo_pago')
        .annotate(cantidad=Count('id'))
        .order_by('-cantidad')
    )

    # Ofertas promedio por trabajo
    from trabajos.models import OfertaTrabajo
    total_ofertas = OfertaTrabajo.objects.count()
    ofertas_aceptadas = OfertaTrabajo.objects.filter(status='aceptada').count()

    return {
        'total_trabajos': total_trabajos,
        'trabajos_en_periodo': trabajos_periodo.count(),
        'por_status': [
            {'status': t['status'], 'cantidad': t['cantidad']}
            for t in por_status
        ],
        'urgentes_total': urgentes,
        'urgentes_en_periodo': urgentes_periodo,
        'ingresos_trabajos_finalizados': _decimal_str(ingresos),
        'calificacion_promedio': round(avg_rating, 2),
        'total_calificaciones': total_calificaciones,
        'por_metodo_pago': [
            {'metodo': t['metodo_pago'], 'cantidad': t['cantidad']}
            for t in por_metodo_pago
        ],
        'total_ofertas': total_ofertas,
        'ofertas_aceptadas': ofertas_aceptadas,
        'tasa_aceptacion': round(ofertas_aceptadas / total_ofertas * 100, 2) if total_ofertas > 0 else 0,
    }


def estadisticas_ordenes(start, end):
    """Estadísticas de órdenes/productos."""
    total_ordenes = Orden.objects.count()
    ordenes_periodo = Orden.objects.filter(created_at__gte=start, created_at__lt=end)

    # Por status
    por_status = list(
        Orden.objects.values('status')
        .annotate(cantidad=Count('id'))
        .order_by('-cantidad')
    )

    # Ingresos
    ingresos = Orden.objects.filter(
        status__in=('finalizada', 'entregada', 'aceptada'),
        created_at__gte=start,
        created_at__lt=end,
    ).aggregate(total=Sum('total'))['total'] or Decimal('0')

    # Ticket promedio
    ticket_promedio = ordenes_periodo.filter(
        status__in=('finalizada', 'entregada', 'aceptada')
    ).aggregate(promedio=Avg('total'))['promedio'] or Decimal('0')

    # Top productos vendidos
    top_productos = list(
        OrdenItem.objects.filter(
            orden__created_at__gte=start,
            orden__created_at__lt=end,
            orden__status__in=('finalizada', 'entregada', 'aceptada'),
        )
        .values('producto__nombre')
        .annotate(
            cantidad=Sum('cantidad'),
            ingreso=Sum('subtotal'),
        )
        .order_by('-ingreso')[:10]
    )

    # Por método de pago
    por_metodo = list(
        Orden.objects.exclude(metodo_pago__isnull=True)
        .values('metodo_pago')
        .annotate(cantidad=Count('id'))
        .order_by('-cantidad')
    )

    return {
        'total_ordenes': total_ordenes,
        'ordenes_en_periodo': ordenes_periodo.count(),
        'por_status': [
            {'status': o['status'], 'cantidad': o['cantidad']}
            for o in por_status
        ],
        'ingresos_ordenes': _decimal_str(ingresos),
        'ticket_promedio': _decimal_str(ticket_promedio),
        'top_productos': [
            {
                'producto': p['producto__nombre'],
                'cantidad': p['cantidad'] or 0,
                'ingreso': _decimal_str(p['ingreso']),
            }
            for p in top_productos
        ],
        'por_metodo_pago': [
            {'metodo': o['metodo_pago'], 'cantidad': o['cantidad']}
            for o in por_metodo
        ],
    }


def estadisticas_pagos(start, end):
    """Estadísticas de pagos."""
    total_pagos = Pago.objects.count()
    pagos_periodo = Pago.objects.filter(created_at__gte=start, created_at__lt=end)

    # Por status
    por_status = list(
        Pago.objects.values('status')
        .annotate(cantidad=Count('id'))
        .order_by('-cantidad')
    )

    # Montos
    montos = Pago.objects.filter(
        status='aprobado',
        created_at__gte=start,
        created_at__lt=end,
    ).aggregate(
        total=Sum('monto'),
        comision=Sum('comision_plataforma'),
        vendedor=Sum('monto_vendedor'),
    )

    # Por tipo (orden vs trabajo)
    por_tipo = list(
        Pago.objects.values('tipo')
        .annotate(
            cantidad=Count('id'),
            monto_total=Sum('monto'),
        )
        .order_by('-cantidad')
    )

    return {
        'total_pagos': total_pagos,
        'pagos_en_periodo': pagos_periodo.count(),
        'por_status': [
            {'status': p['status'], 'cantidad': p['cantidad']}
            for p in por_status
        ],
        'monto_total_aprobado': _decimal_str(montos['total']),
        'comision_plataforma': _decimal_str(montos['comision']),
        'monto_a_vendedores': _decimal_str(montos['vendedor']),
        'por_tipo': [
            {
                'tipo': p['tipo'],
                'cantidad': p['cantidad'],
                'monto_total': _decimal_str(p['monto_total']),
            }
            for p in por_tipo
        ],
    }


def estadisticas_survey():
    """Estadísticas de encuestas (landing page)."""
    total = SurveyResponse.objects.count()

    # Por intención de uso
    por_intencion = list(
        SurveyResponse.objects.values('likelihood')
        .annotate(cantidad=Count('id'))
        .order_by('-cantidad')
    )

    # Por rol
    por_rol = list(
        SurveyResponse.objects.values('role')
        .annotate(cantidad=Count('id'))
        .order_by('-cantidad')
    )

    # Dispuestos a pagar (solo profesionales)
    dispuestos_pagar = SurveyResponse.objects.filter(willing_to_pay=True).count()

    return {
        'total_respuestas': total,
        'por_intencion': [
            {'intencion': s['likelihood'], 'cantidad': s['cantidad']}
            for s in por_intencion
        ],
        'por_rol': [
            {'rol': s['role'], 'cantidad': s['cantidad']}
            for s in por_rol
        ],
        'profesionales_dispuestos_a_pagar': dispuestos_pagar,
    }


def estadisticas_mensajeria(start, end):
    """Estadísticas de mensajería/chat."""
    total_chats = Chat.objects.count()
    total_mensajes = Mensajes.objects.count()
    mensajes_periodo = Mensajes.objects.filter(created_at__gte=start, created_at__lt=end).count()

    # Mensajes no leídos
    no_leidos = Mensajes.objects.filter(leido=False).count()

    return {
        'total_chats': total_chats,
        'total_mensajes': total_mensajes,
        'mensajes_en_periodo': mensajes_periodo,
        'mensajes_no_leidos': no_leidos,
    }


def estadisticas_resumen(start, end):
    """Resumen ejecutivo del sistema."""
    ahora = timezone.now()

    return {
        'usuarios': {
            'total': Usuario.objects.count(),
            'nuevos_en_periodo': Usuario.objects.filter(created_at__gte=start, created_at__lt=end).count(),
        },
        'suscripciones': {
            'activas': Subscripcion.objects.filter(cancelada=False, expiracion__gt=ahora).count(),
            'nuevas_en_periodo': Subscripcion.objects.filter(created_at__gte=start, created_at__lt=end).count(),
        },
        'empresas': {
            'total': Empresa.objects.count(),
            'nuevas_en_periodo': Empresa.objects.filter(created_at__gte=start, created_at__lt=end).count(),
        },
        'trabajos': {
            'total': Trabajo.objects.count(),
            'en_periodo': Trabajo.objects.filter(created_at__gte=start, created_at__lt=end).count(),
            'finalizados': Trabajo.objects.filter(status='finalizado').count(),
        },
        'ordenes': {
            'total': Orden.objects.count(),
            'en_periodo': Orden.objects.filter(created_at__gte=start, created_at__lt=end).count(),
        },
        'pagos': {
            'total_aprobado': _decimal_str(
                Pago.objects.filter(status='aprobado', created_at__gte=start, created_at__lt=end)
                .aggregate(t=Sum('monto'))['t'] or Decimal('0')
            ),
        },
        'encuestas': {
            'total': SurveyResponse.objects.count(),
        },
    }


def estadisticas_globales(request) -> dict:
    """Endpoint principal: todas las estadísticas para el admin dashboard."""
    year, month, last_day, start, end = _parse_period(request)

    meses_es = [
        '', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
        'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre',
    ]

    return {
        'periodo': {
            'year': year,
            'month': month,
            'label': f'{meses_es[month]} {year}',
            'dias_en_mes': last_day,
        },
        'resumen': estadisticas_resumen(start, end),
        'usuarios': estadisticas_usuarios(start, end),
        'suscripciones': estadisticas_suscripciones(start, end),
        'planes': estadisticas_planes(),
        'empresas': estadisticas_empresas(start, end),
        'trabajos': estadisticas_trabajos(start, end),
        'ordenes': estadisticas_ordenes(start, end),
        'pagos': estadisticas_pagos(start, end),
        'encuestas': estadisticas_survey(),
        'mensajeria': estadisticas_mensajeria(start, end),
    }
