from django.core.management.base import BaseCommand
from datetime import timedelta
from suscripciones.models import Plan

class Command(BaseCommand):
    help = 'Crea los planes iniciales del sistema'

    def handle(self, *args, **kwargs):
        planes = [
            {
                'nombre': 'Gratuito',
                'descripcion': 'Plan gratuito incluido al crear tu cuenta. Ideal para empezar.',
                'precio': 0.00,
                'cantidad_personas': 1,
                'duracion': timedelta(days=36500),
                'cantidad_jobs': 5,
                'activo': True,
                'caracteristicas': [
                    'Hasta 5 trabajos',
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
                'cantidad_jobs': 20,
                'activo': True,
                'caracteristicas': [
                    'Hasta 20 trabajos por mes',
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
                'cantidad_jobs': 100,
                'activo': True,
                'caracteristicas': [
                    'Hasta 100 trabajos por mes',
                    'Acceso prioritario al mapa de profesionales',
                    'Soporte prioritario',
                    'Estadísticas de uso',
                ],
            },
        ]

        for plan_data in planes:
            plan, created = Plan.objects.get_or_create(
                nombre=plan_data['nombre'],
                defaults=plan_data
            )
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f'✓ Plan "{plan.nombre}" creado ({plan.cantidad_jobs} jobs)')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'- Plan "{plan.nombre}" ya existe')
                )

        self.stdout.write(
            self.style.SUCCESS('\n✅ Seed de planes completado')
        )