from decimal import Decimal

from django.core.management.base import BaseCommand
from datetime import timedelta
from suscripciones.models import Plan


PLANES_SEED = [
    {
        'nombre': 'Gratuito',
        'descripcion': 'Plan gratuito incluido al crear tu cuenta. Ideal para empezar.',
        'precio': 0.00,
        'cantidad_personas': 1,
        'duracion': timedelta(days=36500),
        'cantidad_jobs': 20,
        'activo': True,
        'google_play_id': '',
        'appstore_id': '',
        'caracteristicas': [
            'Hasta 20 trabajos',
            'Acceso al mapa de profesionales',
            'Soporte básico',
        ],
        'tiene_landing_page': False,
    },
    {
        'nombre': 'Básico',
        'descripcion': 'Plan mensual con acceso a más trabajos y funcionalidades.',
        'precio': 9.99,
        'cantidad_personas': 1,
        'duracion': timedelta(days=30),
        'cantidad_jobs': 200,
        'activo': True,
        'google_play_id': 'alavuelta_monthly',
        'appstore_id': 'com.alavueltaapp.basico.monthly',
        'caracteristicas': [
            'Hasta 200 trabajos por mes',
            'Acceso al mapa de profesionales',
            'Soporte estándar',
        ],
        'tiene_landing_page': False,
    },
    {
        'nombre': 'Pro',
        'descripcion': 'Plan mensual para usuarios frecuentes con trabajos ilimitados.',
        'precio': 24.99,
        'cantidad_personas': 1,
        'duracion': timedelta(days=30),
        'cantidad_jobs': 1000,
        'activo': True,
        'google_play_id': 'alavuelta_monthly_pro',
        'appstore_id': 'com.alavueltaapp.pro.monthly',
        'caracteristicas': [
            'Hasta 1000 trabajos por mes',
            'Acceso prioritario al mapa de profesionales',
            'Soporte prioritario',
            'Estadísticas de uso',
            'Landing page propia',
        ],
        'tiene_landing_page': True,
    },
]

_STORE_FIELDS = ('google_play_id', 'appstore_id')


def _defaults_from_seed(plan_data):
    """Valores listos para create/update (sin nombre; precio como Decimal; IDs vacíos → None)."""
    out = {}
    for key, value in plan_data.items():
        if key == 'nombre':
            continue
        if key == 'precio':
            out[key] = Decimal(str(value))
        elif key in _STORE_FIELDS:
            out[key] = value or None
        else:
            out[key] = value
    return out


class Command(BaseCommand):
    help = (
        'Crea o actualiza los planes desde PLANES_SEED (precio, descripción, jobs, tiendas, etc.). '
        'La clave natural es nombre.'
    )

    def handle(self, *args, **kwargs):
        for plan_data in PLANES_SEED:
            defaults = _defaults_from_seed(plan_data)
            plan, created = Plan.objects.get_or_create(
                nombre=plan_data['nombre'],
                defaults=defaults,
            )
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f'✓ Plan "{plan.nombre}" creado ({plan.cantidad_jobs} jobs)')
                )
                continue

            changed_fields = []
            for field, new_value in defaults.items():
                current = getattr(plan, field)
                if current != new_value:
                    setattr(plan, field, new_value)
                    changed_fields.append(field)

            if changed_fields:
                plan.save()
                self.stdout.write(
                    self.style.WARNING(
                        f'~ Plan "{plan.nombre}" actualizado: {", ".join(changed_fields)}'
                    )
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'- Plan "{plan.nombre}" sin cambios')
                )

        self.stdout.write(
            self.style.SUCCESS('\n✅ Seed de planes completado')
        )
