from .models import Profesion

VENDEDOR_PROFESION_NOMBRE = 'Vendedor@'
VENDEDOR_PROFESION_DESCRIPCION = 'Venta de productos, menú diario y catálogo online'


def obtener_profesion_por_id(profesion_id):
    try:
        return Profesion.objects.get(id=profesion_id)
    except Profesion.DoesNotExist:
        return None


def obtener_profesiones_por_ids(profesion_ids):
    return Profesion.objects.filter(id__in=profesion_ids)


def get_or_create_vendedor_profesion():
    """Profesión default para empresas que venden productos."""
    profesion, _ = Profesion.objects.get_or_create(
        nombre=VENDEDOR_PROFESION_NOMBRE,
        defaults={
            'descripcion': VENDEDOR_PROFESION_DESCRIPCION,
            'logo_svg_url': '',
        },
    )
    return profesion

