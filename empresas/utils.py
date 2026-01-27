from .models import Empresa
from localizacion.models import Localizacion


def validar_nombre_empresa_unico(nombre):
    return not Empresa.objects.filter(nombre__iexact=nombre).exists()


def crear_empresa(nombre, ubicacion, latitud, longitud, admin_id, descripcion='', unipersonal=False, localizacion=None):
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
        admin_id=admin_id
    )
    
    return empresa
