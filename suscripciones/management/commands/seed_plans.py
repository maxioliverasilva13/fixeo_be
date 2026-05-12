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
    },
    {
        'nombre': 'Básico',
        'descripcion': 'Plan mensual con acceso a más trabajos y funcionalidades.',
        'precio': 9.99,
        'cantidad_personas': 1,
        'duracion': timedelta(days=30),
        'cantidad_jobs': 200,
        'activo': True,
        'google_play_id': 'fixeo_basico_monthly',
        'appstore_id': 'com.alavueltaapp.basico.monthly',
        'caracteristicas': [
            'Hasta 200 trabajos por mes',
            'Acceso al mapa de profesionales',
            'Soporte estándar',
        ],
    },
    {
        'nombre': 'Pro',
        'descripcion': 'Plan mensual para usuarios frecuentes con trabajos ilimitados.',
        'precio': 24.99,
        'cantidad_personas': 1,
        'duracion': timedelta(days=30),
        'cantidad_jobs': 1000,
        'activo': True,
        'google_play_id': 'fixeo_pro_monthly',
        'appstore_id': 'com.alavueltaapp.pro.monthly',
        'caracteristicas': [
            'Hasta 1000 trabajos por mes',
            'Acceso prioritario al mapa de profesionales',
            'Soporte prioritario',
            'Estadísticas de uso',
        ],
    },
]


class Command(BaseCommand):
    help = 'Crea los planes iniciales del sistema (incluyendo IDs de Google Play y App Store)'

    def handle(self, *args, **kwargs):
        for plan_data in PLANES_SEED:
            plan, created = Plan.objects.get_or_create(
                nombre=plan_data['nombre'],
                defaults=plan_data,
            )
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f'✓ Plan "{plan.nombre}" creado ({plan.cantidad_jobs} jobs)')
                )
            else:
                # Mantener IDs de Google Play / App Store al día sin pisar otros campos manuales
                changed = False
                for field in ('google_play_id', 'appstore_id'):
                    new_value = plan_data.get(field, '') or ''
                    if (getattr(plan, field) or '') != new_value:
                        setattr(plan, field, new_value or None)
                        changed = True
                if changed:
                    plan.save(update_fields=['google_play_id', 'appstore_id', 'updated_at'])
                    self.stdout.write(
                        self.style.WARNING(
                            f'~ Plan "{plan.nombre}" actualizado (IDs de tienda)'
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(f'- Plan "{plan.nombre}" ya existe')
                    )

        self.stdout.write(
            self.style.SUCCESS('\n✅ Seed de planes completado')
        )