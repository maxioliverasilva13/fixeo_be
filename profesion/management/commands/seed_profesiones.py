from django.core.management.base import BaseCommand
from profesion.models import Profesion


class Command(BaseCommand):
    help = 'Crea profesiones de ejemplo en la base de datos'

    def handle(self, *args, **kwargs):
        profesiones = [
            {
                'nombre': 'Plomero',
                'descripcion': 'Instalación y reparación de sistemas de agua, gas y desagües',
                'logo_svg_url': 'https://example.com/icons/plomero.svg'
            },
            {
                'nombre': 'Electricista',
                'descripcion': 'Instalación y mantenimiento de sistemas eléctricos residenciales y comerciales',
                'logo_svg_url': 'https://example.com/icons/electricista.svg'
            },
            {
                'nombre': 'Carpintero',
                'descripcion': 'Construcción y reparación de estructuras de madera y muebles',
                'logo_svg_url': 'https://example.com/icons/carpintero.svg'
            },
            {
                'nombre': 'Pintor',
                'descripcion': 'Pintura de interiores y exteriores, empapelado y acabados',
                'logo_svg_url': 'https://example.com/icons/pintor.svg'
            },
            {
                'nombre': 'Albañil',
                'descripcion': 'Construcción y reparación de estructuras de mampostería',
                'logo_svg_url': 'https://example.com/icons/albanil.svg'
            },
            {
                'nombre': 'Gasista',
                'descripcion': 'Instalación y mantenimiento de sistemas de gas natural y envasado',
                'logo_svg_url': 'https://example.com/icons/gasista.svg'
            },
            {
                'nombre': 'Jardinero',
                'descripcion': 'Diseño, mantenimiento y cuidado de jardines y espacios verdes',
                'logo_svg_url': 'https://example.com/icons/jardinero.svg'
            },
            {
                'nombre': 'Cerrajero',
                'descripcion': 'Instalación, reparación y apertura de cerraduras y sistemas de seguridad',
                'logo_svg_url': 'https://example.com/icons/cerrajero.svg'
            },
            {
                'nombre': 'Técnico en Refrigeración',
                'descripcion': 'Instalación y reparación de equipos de aire acondicionado y refrigeración',
                'logo_svg_url': 'https://example.com/icons/refrigeracion.svg'
            },
            {
                'nombre': 'Techista',
                'descripcion': 'Instalación y reparación de techos, tejas y membranas',
                'logo_svg_url': 'https://example.com/icons/techista.svg'
            },
            {
                'nombre': 'Herrero',
                'descripcion': 'Fabricación e instalación de estructuras metálicas, rejas y portones',
                'logo_svg_url': 'https://example.com/icons/herrero.svg'
            },
            {
                'nombre': 'Vidriero',
                'descripcion': 'Instalación y reparación de vidrios, espejos y cristales',
                'logo_svg_url': 'https://example.com/icons/vidriero.svg'
            },
            {
                'nombre': 'Fumigador',
                'descripcion': 'Control de plagas y desinfección de espacios',
                'logo_svg_url': 'https://example.com/icons/fumigador.svg'
            },
            {
                'nombre': 'Limpieza',
                'descripcion': 'Servicios de limpieza residencial y comercial',
                'logo_svg_url': 'https://example.com/icons/limpieza.svg'
            },
            {
                'nombre': 'Mudanzas',
                'descripcion': 'Servicios de traslado y embalaje de muebles y pertenencias',
                'logo_svg_url': 'https://example.com/icons/mudanzas.svg'
            },
            {
                'nombre': 'Tapicero',
                'descripcion': 'Reparación y renovación de tapizados de muebles',
                'logo_svg_url': 'https://example.com/icons/tapicero.svg'
            },
            {
                'nombre': 'Parquetista',
                'descripcion': 'Instalación y restauración de pisos de madera',
                'logo_svg_url': 'https://example.com/icons/parquetista.svg'
            },
            {
                'nombre': 'Colocador de Durlock',
                'descripcion': 'Instalación de placas de yeso y cielorrasos',
                'logo_svg_url': 'https://example.com/icons/durlock.svg'
            },
            {
                'nombre': 'Instalador de Pisos',
                'descripcion': 'Colocación de cerámicos, porcelanatos y pisos flotantes',
                'logo_svg_url': 'https://example.com/icons/pisos.svg'
            },
            {
                'nombre': 'Mecánico',
                'descripcion': 'Reparación y mantenimiento de vehículos',
                'logo_svg_url': 'https://example.com/icons/mecanico.svg'
            },
            {
                'nombre': 'Gomería',
                'descripcion': 'Reparación y cambio de neumáticos',
                'logo_svg_url': 'https://example.com/icons/gomeria.svg'
            },
            {
                'nombre': 'Lavadero de Autos',
                'descripcion': 'Limpieza y detailing de vehículos',
                'logo_svg_url': 'https://example.com/icons/lavadero.svg'
            },
            {
                'nombre': 'Técnico en Computación',
                'descripcion': 'Reparación y mantenimiento de equipos informáticos',
                'logo_svg_url': 'https://example.com/icons/computacion.svg'
            },
            {
                'nombre': 'Técnico en Celulares',
                'descripcion': 'Reparación de teléfonos móviles y tablets',
                'logo_svg_url': 'https://example.com/icons/celulares.svg'
            },
            {
                'nombre': 'Instalador de Alarmas',
                'descripcion': 'Instalación y mantenimiento de sistemas de seguridad',
                'logo_svg_url': 'https://example.com/icons/alarmas.svg'
            },
            {
                'nombre': 'Instalador de Cámaras',
                'descripcion': 'Instalación de sistemas de videovigilancia',
                'logo_svg_url': 'https://example.com/icons/camaras.svg'
            },
            {
                'nombre': 'Paseador de Perros',
                'descripcion': 'Servicios de paseo y cuidado de mascotas',
                'logo_svg_url': 'https://example.com/icons/paseador.svg'
            },
            {
                'nombre': 'Veterinario',
                'descripcion': 'Atención médica y cuidado de animales',
                'logo_svg_url': 'https://example.com/icons/veterinario.svg'
            },
            {
                'nombre': 'Peluquero Canino',
                'descripcion': 'Servicios de estética y cuidado para mascotas',
                'logo_svg_url': 'https://example.com/icons/peluquero-canino.svg'
            },
            {
                'nombre': 'Instructor de Fitness',
                'descripcion': 'Entrenamiento personal y clases de ejercicio',
                'logo_svg_url': 'https://example.com/icons/fitness.svg'
            },
        ]

        created_count = 0
        updated_count = 0

        for profesion_data in profesiones:
            profesion, created = Profesion.objects.get_or_create(
                nombre=profesion_data['nombre'],
                defaults={
                    'descripcion': profesion_data['descripcion'],
                    'logo_svg_url': profesion_data['logo_svg_url']
                }
            )
            
            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f'✓ Profesión "{profesion.nombre}" creada'))
            else:
                # Actualizar descripción y logo si ya existe
                profesion.descripcion = profesion_data['descripcion']
                profesion.logo_svg_url = profesion_data['logo_svg_url']
                profesion.save()
                updated_count += 1
                self.stdout.write(self.style.WARNING(f'↻ Profesión "{profesion.nombre}" actualizada'))

        self.stdout.write(self.style.SUCCESS(f'\n✅ Seed de profesiones completado'))
        self.stdout.write(self.style.SUCCESS(f'   Creadas: {created_count}'))
        self.stdout.write(self.style.SUCCESS(f'   Actualizadas: {updated_count}'))
