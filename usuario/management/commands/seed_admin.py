from django.core.management.base import BaseCommand
from django.db import transaction
from usuario.models import Usuario
from rol.models import Rol


class Command(BaseCommand):
    help = 'Crea el usuario admin inicial (alavueltapp@gmail.com)'

    def handle(self, *args, **kwargs):
        with transaction.atomic():
            # Asegurar que exista el rol admin
            rol_admin, _ = Rol.objects.get_or_create(
                nombre='admin',
                defaults={'nombre': 'admin'}
            )

            # Crear o actualizar el usuario admin
            admin, created = Usuario.objects.get_or_create(
                correo='alavueltapp@gmail.com',
                defaults={
                    'nombre': 'Admin',
                    'apellido': 'AlaVuelta',
                    'telefono': '',
                    'is_staff': True,
                    'is_superuser': True,
                    'is_active': True,
                    'is_owner_empresa': False,
                    'rol': rol_admin,
                }
            )

            if created:
                admin.set_password('AdminFixeo2025!')
                admin.save(update_fields=['password'])
                self.stdout.write(
                    self.style.SUCCESS(
                        f'✓ Admin creado: {admin.correo} | password: AdminFixeo2025!'
                    )
                )
            else:
                # Asegurar que tenga privilegios de admin
                admin.is_staff = True
                admin.is_superuser = True
                admin.is_active = True
                admin.rol = rol_admin
                admin.save(update_fields=['is_staff', 'is_superuser', 'is_active', 'rol'])
                self.stdout.write(
                    self.style.WARNING(
                        f'- Admin ya existía, privilegios actualizados: {admin.correo}'
                    )
                )

            self.stdout.write(
                self.style.SUCCESS('\n✅ Seed de admin completado')
            )
