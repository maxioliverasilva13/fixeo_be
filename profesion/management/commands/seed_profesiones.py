from django.core.management.base import BaseCommand
from profesion.models import Profesion


class Command(BaseCommand):
    help = 'Crea profesiones de ejemplo en la base de datos'

    def handle(self, *args, **kwargs):
        profesiones = [
            {
                'nombre': 'Plomero',
                'descripcion': 'Instalación y reparación de sistemas de agua, gas y desagües',
                'logo_svg_url': 'https://dibvhmpmocsmqvlemcqk.supabase.co/storage/v1/object/public/bucketFixea/iconsProfesiones/Rodrigo-Olivera-CV.png'
            },
            {
                'nombre': 'Electricista',
                'descripcion': 'Instalación y mantenimiento de sistemas eléctricos residenciales y comerciales',
                'logo_svg_url': 'https://dibvhmpmocsmqvlemcqk.supabase.co/storage/v1/object/public/bucketFixea/iconsProfesiones/bolt%20(1).png'
            },
            {
                'nombre': 'Carpintero',
                'descripcion': 'Construcción y reparación de estructuras de madera y muebles',
                'logo_svg_url': 'https://dibvhmpmocsmqvlemcqk.supabase.co/storage/v1/object/public/bucketFixea/iconsProfesiones/saw.png'
            },
            {
                'nombre': 'Pintor',
                'descripcion': 'Pintura de interiores y exteriores, empapelado y acabados',
                'logo_svg_url': 'https://dibvhmpmocsmqvlemcqk.supabase.co/storage/v1/object/public/bucketFixea/iconsProfesiones/paint-roller.png'
            },
            {
                'nombre': 'Albañil',
                'descripcion': 'Construcción y reparación de estructuras de mampostería',
                'logo_svg_url': 'https://dibvhmpmocsmqvlemcqk.supabase.co/storage/v1/object/public/bucketFixea/iconsProfesiones/building-materials.png'
            },
            {
                'nombre': 'Gasista',
                'descripcion': 'Instalación y mantenimiento de sistemas de gas natural y envasado',
                'logo_svg_url': 'https://dibvhmpmocsmqvlemcqk.supabase.co/storage/v1/object/public/bucketFixea/iconsProfesiones/plumbing.png'
            },
            {
                'nombre': 'Jardinero',
                'descripcion': 'Diseño, mantenimiento y cuidado de jardines y espacios verdes',
                'logo_svg_url': 'https://dibvhmpmocsmqvlemcqk.supabase.co/storage/v1/object/public/bucketFixea/iconsProfesiones/daisy-alt.png'
            },
            {
                'nombre': 'Cerrajero',
                'descripcion': 'Instalación, reparación y apertura de cerraduras y sistemas de seguridad',
                'logo_svg_url': 'https://dibvhmpmocsmqvlemcqk.supabase.co/storage/v1/object/public/bucketFixea/iconsProfesiones/key.png'
            },
            {
                'nombre': 'Técnico en Refrigeración',
                'descripcion': 'Instalación y reparación de equipos de aire acondicionado y refrigeración',
                'logo_svg_url': 'https://dibvhmpmocsmqvlemcqk.supabase.co/storage/v1/object/public/bucketFixea/iconsProfesiones/air-conditioner.png'
            },
            {
                'nombre': 'Techista',
                'descripcion': 'Instalación y reparación de techos, tejas y membranas',
                'logo_svg_url': 'https://dibvhmpmocsmqvlemcqk.supabase.co/storage/v1/object/public/bucketFixea/iconsProfesiones/roof.png'
            },
            {
                'nombre': 'Herrero',
                'descripcion': 'Fabricación e instalación de estructuras metálicas, rejas y portones',
                'logo_svg_url': 'https://dibvhmpmocsmqvlemcqk.supabase.co/storage/v1/object/public/bucketFixea/iconsProfesiones/rock-hammer.png'
            },
            {
                'nombre': 'Vidriero',
                'descripcion': 'Instalación y reparación de vidrios, espejos y cristales',
                'logo_svg_url': 'https://dibvhmpmocsmqvlemcqk.supabase.co/storage/v1/object/public/bucketFixea/iconsProfesiones/house-window.png'
            },
            {
                'nombre': 'Fumigador',
                'descripcion': 'Control de plagas y desinfección de espacios',
                'logo_svg_url': 'https://dibvhmpmocsmqvlemcqk.supabase.co/storage/v1/object/public/bucketFixea/iconsProfesiones/spray-can.png'
            },
            {
                'nombre': 'Limpieza',
                'descripcion': 'Servicios de limpieza residencial y comercial',
                'logo_svg_url': 'https://dibvhmpmocsmqvlemcqk.supabase.co/storage/v1/object/public/bucketFixea/iconsProfesiones/broom.png'
            },
            {
                'nombre': 'Mudanzas',
                'descripcion': 'Servicios de traslado y embalaje de muebles y pertenencias',
                'logo_svg_url': 'https://dibvhmpmocsmqvlemcqk.supabase.co/storage/v1/object/public/bucketFixea/iconsProfesiones/box-open.png'
            },
            {
                'nombre': 'Tapicero',
                'descripcion': 'Reparación y renovación de tapizados de muebles',
                'logo_svg_url': 'https://dibvhmpmocsmqvlemcqk.supabase.co/storage/v1/object/public/bucketFixea/iconsProfesiones/loveseat.png'
            },
            {
                'nombre': 'Parquetista',
                'descripcion': 'Instalación y restauración de pisos de madera',
                'logo_svg_url': 'https://dibvhmpmocsmqvlemcqk.supabase.co/storage/v1/object/public/bucketFixea/iconsProfesiones/floor-layer.png'
            },
            {
                'nombre': 'Colocador de Durlock',
                'descripcion': 'Instalación de placas de yeso y cielorrasos',
                'logo_svg_url': 'https://dibvhmpmocsmqvlemcqk.supabase.co/storage/v1/object/public/bucketFixea/iconsProfesiones/floor-layer.png'
            },
            {
                'nombre': 'Instalador de Pisos',
                'descripcion': 'Colocación de cerámicos, porcelanatos y pisos flotantes',
                'logo_svg_url': 'https://dibvhmpmocsmqvlemcqk.supabase.co/storage/v1/object/public/bucketFixea/iconsProfesiones/floor-layer.png'
            },
            {
                'nombre': 'Mecánico',
                'descripcion': 'Reparación y mantenimiento de vehículos',
                'logo_svg_url': 'https://dibvhmpmocsmqvlemcqk.supabase.co/storage/v1/object/public/bucketFixea/iconsProfesiones/car-mechanic.png'
            },
            {
                'nombre': 'Gomería',
                'descripcion': 'Reparación y cambio de neumáticos',
                'logo_svg_url': 'https://dibvhmpmocsmqvlemcqk.supabase.co/storage/v1/object/public/bucketFixea/iconsProfesiones/tire.png'
            },
            {
                'nombre': 'Lavadero de Autos',
                'descripcion': 'Limpieza y detailing de vehículos',
                'logo_svg_url': 'https://dibvhmpmocsmqvlemcqk.supabase.co/storage/v1/object/public/bucketFixea/iconsProfesiones/car-wash.png'
            },
            {
                'nombre': 'Técnico en Computación',
                'descripcion': 'Reparación y mantenimiento de equipos informáticos',
                'logo_svg_url': 'https://dibvhmpmocsmqvlemcqk.supabase.co/storage/v1/object/public/bucketFixea/iconsProfesiones/computer.png'
            },
            {
                'nombre': 'Técnico en Celulares',
                'descripcion': 'Reparación de teléfonos móviles y tablets',
                'logo_svg_url': 'https://dibvhmpmocsmqvlemcqk.supabase.co/storage/v1/object/public/bucketFixea/iconsProfesiones/smartphone.png'
            },
            {
                'nombre': 'Instalador de Alarmas',
                'descripcion': 'Instalación y mantenimiento de sistemas de seguridad',
                'logo_svg_url': 'https://dibvhmpmocsmqvlemcqk.supabase.co/storage/v1/object/public/bucketFixea/iconsProfesiones/camera-cctv.png'
            },
            {
                'nombre': 'Instalador de Cámaras',
                'descripcion': 'Instalación de sistemas de videovigilancia',
                'logo_svg_url': 'https://dibvhmpmocsmqvlemcqk.supabase.co/storage/v1/object/public/bucketFixea/iconsProfesiones/dog-leashed.png'
            },
            {
                'nombre': 'Paseador de Perros',
                'descripcion': 'Servicios de paseo y cuidado de mascotas',
                'logo_svg_url': 'https://dibvhmpmocsmqvlemcqk.supabase.co/storage/v1/object/public/bucketFixea/iconsProfesiones/light-emergency.png'
            },
            {
                'nombre': 'Veterinario',
                'descripcion': 'Atención médica y cuidado de animales',
                'logo_svg_url': 'https://dibvhmpmocsmqvlemcqk.supabase.co/storage/v1/object/public/bucketFixea/iconsProfesiones/paw-heart.png'
            },
            {
                'nombre': 'Peluquero Canino',
                'descripcion': 'Servicios de estética y cuidado para mascotas',
                'logo_svg_url': 'https://dibvhmpmocsmqvlemcqk.supabase.co/storage/v1/object/public/bucketFixea/iconsProfesiones/barber-shop.png'
            },
            {
                'nombre': 'Instructor de Fitness',
                'descripcion': 'Entrenamiento personal y clases de ejercicio',
                'logo_svg_url': 'https://dibvhmpmocsmqvlemcqk.supabase.co/storage/v1/object/public/bucketFixea/iconsProfesiones/gym.png'
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
