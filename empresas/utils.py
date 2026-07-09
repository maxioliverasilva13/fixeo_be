from .models import Empresa
from localizacion.models import Localizacion
import re
import unicodedata


def slugify_subdomain(nombre: str) -> str:
    if not nombre:
        return 'empresa'
    s = unicodedata.normalize('NFKD', nombre)
    s = ''.join(c for c in s if not unicodedata.combining(c))
    s = s.lower().strip()
    s = re.sub(r'[^a-z0-9]+', '-', s)
    s = re.sub(r'-+', '-', s).strip('-')
    return (s[:80] or 'empresa')


def generar_subdomain_unico(nombre: str, exclude_id=None) -> str:
    base = slugify_subdomain(nombre)
    candidate = base
    i = 2
    qs = Empresa.objects.filter(subdomain=candidate)
    if exclude_id:
        qs = qs.exclude(id=exclude_id)
    while qs.exists():
        candidate = f'{base}-{i}'
        qs = Empresa.objects.filter(subdomain=candidate)
        if exclude_id:
            qs = qs.exclude(id=exclude_id)
        i += 1
    return candidate


def validar_nombre_empresa_unico(nombre):
    return not Empresa.objects.filter(nombre__iexact=nombre).exists()


def crear_empresa(
    nombre,
    ubicacion,
    latitud,
    longitud,
    admin_id,
    descripcion='',
    unipersonal=False,
    localizacion=None,
    *,
    vende_productos=False,
    vende_servicios=True,
    compartir_ubicacion_mapa=True,
):
    if not validar_nombre_empresa_unico(nombre):
        raise ValueError(f"Ya existe una empresa con el nombre '{nombre}'")

    empresa = Empresa.objects.create(
        nombre=nombre,
        ubicacion=ubicacion,
        descripcion=descripcion,
        latitud=latitud,
        longitud=longitud,
        unipersonal=unipersonal,
        localizacion=localizacion,
        admin_id=admin_id,
        vende_productos=vende_productos,
        vende_servicios=vende_servicios,
        compartir_ubicacion_mapa=compartir_ubicacion_mapa,
        subdomain=generar_subdomain_unico(nombre),
    )
    
    return empresa
