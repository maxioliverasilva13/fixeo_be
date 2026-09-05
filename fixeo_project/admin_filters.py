"""
Helpers compartidos para filtros de listados del panel admin.
"""
from calendar import monthrange
from datetime import datetime, timedelta

from django.utils import timezone


def apply_created_at_filters(queryset, params):
    """
    Aplica filtros de creación por year/month o created_from/created_to,
    y filtro de empresas/usuarios recientes (nuevas=true → últimos N días).
    """
    year = params.get('year')
    month = params.get('month')
    if year:
        try:
            year_i = int(year)
            queryset = queryset.filter(created_at__year=year_i)
            if month:
                month_i = max(1, min(12, int(month)))
                queryset = queryset.filter(created_at__month=month_i)
        except (TypeError, ValueError):
            pass

    created_from = params.get('created_from')
    created_to = params.get('created_to')
    if created_from:
        try:
            start = timezone.make_aware(datetime.fromisoformat(created_from[:10]))
            queryset = queryset.filter(created_at__gte=start)
        except (TypeError, ValueError):
            pass
    if created_to:
        try:
            end_day = datetime.fromisoformat(created_to[:10])
            end = timezone.make_aware(datetime(end_day.year, end_day.month, end_day.day, 23, 59, 59))
            queryset = queryset.filter(created_at__lte=end)
        except (TypeError, ValueError):
            pass

    nuevas = params.get('nuevas')
    if nuevas is not None and str(nuevas).lower() in ('1', 'true', 'yes'):
        try:
            days = int(params.get('nuevas_dias', 7))
        except (TypeError, ValueError):
            days = 7
        days = max(1, min(90, days))
        since = timezone.now() - timedelta(days=days)
        queryset = queryset.filter(created_at__gte=since)

    return queryset


def apply_ordering(queryset, params, allowed=None, default='-created_at'):
    """
    ordering=created_at | -created_at | nombre | -nombre ...
    """
    if allowed is None:
        allowed = {'created_at', '-created_at', 'nombre', '-nombre', 'id', '-id'}
    ordering = (params.get('ordering') or default).strip()
    if ordering not in allowed:
        ordering = default
    return queryset.order_by(ordering)


def period_bounds_from_params(params):
    """Devuelve (year, month, start, end) a partir de query params."""
    now = timezone.localtime(timezone.now())
    try:
        year = int(params.get('year', now.year))
        month = int(params.get('month', now.month))
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
