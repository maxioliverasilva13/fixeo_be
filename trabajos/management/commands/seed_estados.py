from django.core.management.base import BaseCommand
from trabajos.models import Estados


class Command(BaseCommand):
    help = 'Crea los estados iniciales del sistema'

    def handle(self, *args, **kwargs):
        estados = [
            {'nombre': 'aceptado', 'finalizador': False},
            {'nombre': 'pendiente', 'finalizador': False},
            {'nombre': 'finalizado', 'finalizador': True},
        ]

        for estado_data in estados:
            estado, created = Estados.objects.get_or_create(
                nombre=estado_data['nombre'],
                defaults=estado_data
            )
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f'✓ Estado "{estado.nombre}" creado')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'- Estado "{estado.nombre}" ya existe')
                )

        self.stdout.write(
            self.style.SUCCESS('\n✅ Seed de estados completado')
        )

