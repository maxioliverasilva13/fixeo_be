from django.core.management.base import BaseCommand
from rol.models import Rol


class Command(BaseCommand):
    help = 'Crea los roles iniciales del sistema'

    def handle(self, *args, **kwargs):
        roles = [
            {'nombre': 'admin'},
            {'nombre': 'usuario'},
            {'nombre': 'profesional'},
        ]

        for rol_data in roles:
            rol, created = Rol.objects.get_or_create(
                nombre=rol_data['nombre'],
                defaults=rol_data
            )
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f'✓ Rol "{rol.nombre}" creado')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'- Rol "{rol.nombre}" ya existe')
                )

        self.stdout.write(
            self.style.SUCCESS('\n✅ Seed de roles completado')
        )
