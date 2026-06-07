"""
Agregados de ingresos y ventas para el panel de estadísticas de empresa.
Solo devuelve datos resumidos (máx. ~31 días + top N) para rendimiento en mobile.
"""
from calendar import monthrange
from datetime import date, datetime
from decimal import Decimal

from django.db.models import Count, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from carritos.models import Orden, OrdenItem
from empresas.models import Empresa
from trabajos.models import Trabajo, TrabajoServicio

ORDEN_INGRESO_STATUSES = ('finalizada', 'entregada', 'aceptada')
TOP_LIMIT = 10


def _decimal_str(value) -> str:
    if value is None:
        return '0.00'
    return f'{Decimal(value):.2f}'


def _parse_period(request):
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


def estadisticas_empresa(empresa: Empresa, request) -> dict:
    year, month, last_day, start, end = _parse_period(request)
    admin = empresa.admin_id
    vende_servicios = empresa.vende_servicios
    vende_productos = empresa.vende_productos

    ingreso_ordenes = Decimal('0')
    ingreso_servicios = Decimal('0')
    cantidad_ordenes = 0
    cantidad_trabajos = 0
    ingreso_diario_map = {d: {'ordenes': Decimal('0'), 'servicios': Decimal('0')} for d in range(1, last_day + 1)}
    top_productos = []
    top_servicios = []
    ordenes_por_estado = {}
    trabajos_por_estado = {}

    if vende_productos:
        ordenes_qs = Orden.objects.filter(
            empresa=empresa,
            created_at__gte=start,
            created_at__lt=end,
        )
        for row in ordenes_qs.values('status').annotate(c=Count('id')):
            ordenes_por_estado[row['status']] = row['c']

        ordenes_ingreso_qs = ordenes_qs.filter(status__in=ORDEN_INGRESO_STATUSES)
        cantidad_ordenes = ordenes_ingreso_qs.count()
        agg = ordenes_ingreso_qs.aggregate(total=Sum('total'))
        ingreso_ordenes = agg['total'] or Decimal('0')

        for row in (
            ordenes_ingreso_qs.annotate(dia=TruncDate('created_at'))
            .values('dia')
            .annotate(monto=Sum('total'))
            .order_by('dia')
        ):
            if row['dia']:
                d = row['dia'].day if hasattr(row['dia'], 'day') else int(str(row['dia'])[-2:])
                if 1 <= d <= last_day:
                    ingreso_diario_map[d]['ordenes'] = row['monto'] or Decimal('0')

        top_productos = list(
            OrdenItem.objects.filter(
                orden__empresa=empresa,
                orden__created_at__gte=start,
                orden__created_at__lt=end,
                orden__status__in=ORDEN_INGRESO_STATUSES,
            )
            .values('producto_id', 'producto__nombre')
            .annotate(
                cantidad=Sum('cantidad'),
                ingreso=Sum('subtotal'),
            )
            .order_by('-ingreso')[:TOP_LIMIT]
        )

    if vende_servicios and admin:
        trabajos_qs = Trabajo.objects.filter(
            profesional=admin,
            created_at__gte=start,
            created_at__lt=end,
        )
        for row in trabajos_qs.values('status').annotate(c=Count('id')):
            trabajos_por_estado[row['status']] = row['c']

        trabajos_ingreso_qs = trabajos_qs.filter(status='finalizado', precio_final__isnull=False)
        cantidad_trabajos = trabajos_ingreso_qs.count()
        agg = trabajos_ingreso_qs.aggregate(total=Sum('precio_final'))
        ingreso_servicios = agg['total'] or Decimal('0')

        for row in (
            trabajos_ingreso_qs.annotate(dia=TruncDate('created_at'))
            .values('dia')
            .annotate(monto=Sum('precio_final'))
            .order_by('dia')
        ):
            if row['dia']:
                d = row['dia'].day if hasattr(row['dia'], 'day') else int(str(row['dia'])[-2:])
                if 1 <= d <= last_day:
                    ingreso_diario_map[d]['servicios'] = row['monto'] or Decimal('0')

        top_servicios = list(
            TrabajoServicio.objects.filter(
                trabajo__profesional=admin,
                trabajo__created_at__gte=start,
                trabajo__created_at__lt=end,
                trabajo__status='finalizado',
            )
            .values('servicio_id', 'servicio__nombre')
            .annotate(
                cantidad=Count('id'),
                ingreso=Sum('precio'),
            )
            .order_by('-ingreso')[:TOP_LIMIT]
        )

    ingreso_diario = []
    for d in range(1, last_day + 1):
        o = ingreso_diario_map[d]['ordenes']
        s = ingreso_diario_map[d]['servicios']
        ingreso_diario.append({
            'dia': d,
            'ordenes': _decimal_str(o),
            'servicios': _decimal_str(s),
            'total': _decimal_str(o + s),
        })

    ingreso_total = ingreso_ordenes + ingreso_servicios
    operaciones = cantidad_ordenes + cantidad_trabajos
    ticket = ingreso_total / operaciones if operaciones else Decimal('0')

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
        'vende_servicios': vende_servicios,
        'vende_productos': vende_productos,
        'resumen': {
            'ingreso_total': _decimal_str(ingreso_total),
            'ingreso_ordenes': _decimal_str(ingreso_ordenes),
            'ingreso_servicios': _decimal_str(ingreso_servicios),
            'cantidad_ordenes': cantidad_ordenes,
            'cantidad_trabajos_finalizados': cantidad_trabajos,
            'ticket_promedio': _decimal_str(ticket),
        },
        'ingreso_diario': ingreso_diario,
        'top_productos': [
            {
                'id': r['producto_id'],
                'nombre': r['producto__nombre'] or 'Sin nombre',
                'cantidad': r['cantidad'] or 0,
                'ingreso': _decimal_str(r['ingreso']),
            }
            for r in top_productos
        ],
        'top_servicios': [
            {
                'id': r['servicio_id'],
                'nombre': r['servicio__nombre'] or 'Sin nombre',
                'cantidad': r['cantidad'] or 0,
                'ingreso': _decimal_str(r['ingreso']),
            }
            for r in top_servicios
        ],
        'ordenes_por_estado': ordenes_por_estado,
        'trabajos_por_estado': trabajos_por_estado,
    }
