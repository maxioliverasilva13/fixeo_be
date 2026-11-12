"""
Catálogo de servicios y horarios "base" por profesión.

Lo usa el endpoint de alta masiva `POST /api/usuarios/registro-base/` (ver
`usuario/views.py::UsuarioViewSet.registro_base`) para que toda cuenta de
profesional creada automáticamente desde la web de prospección arranque, sí o
sí, con al menos un servicio y una grilla de horarios.

Es la única fuente del catálogo base (vive acá, en fixeo_be).

Convenciones:
- `precio` en la divisa `BASE_DIVISA` (ARS, igual que el default del modelo Servicio).
- `tiempo` en minutos (campo `Servicio.tiempo`).
- Las claves de `BASE_SERVICIOS` son el `nombre` EXACTO de la profesión en la
  tabla `profesion` (incluye tildes y símbolos como "Vendedor@").
"""

BASE_DIVISA = 'ARS'

# Grilla horaria por defecto para la empresa unipersonal del profesional base.
# `dia_semana` usa el nombre en inglés en minúsculas, igual que
# `Empresa.esta_abierta_ahora` (ver empresas/models.py), que compara contra
# `datetime.strftime('%A').lower()`.
BASE_HORARIOS = [
    {'dia_semana': 'monday', 'hora_inicio': '09:00', 'hora_fin': '18:00'},
    {'dia_semana': 'tuesday', 'hora_inicio': '09:00', 'hora_fin': '18:00'},
    {'dia_semana': 'wednesday', 'hora_inicio': '09:00', 'hora_fin': '18:00'},
    {'dia_semana': 'thursday', 'hora_inicio': '09:00', 'hora_fin': '18:00'},
    {'dia_semana': 'friday', 'hora_inicio': '09:00', 'hora_fin': '18:00'},
    {'dia_semana': 'saturday', 'hora_inicio': '09:00', 'hora_fin': '13:00'},
]

# Servicios base por profesión. Precios de referencia (editables); la idea es que
# la cuenta quede "completa" y lista para activar y ajustar.
BASE_SERVICIOS = {
    'Plomero': [
        {'nombre': 'Destape de cañería', 'precio': 3500, 'tiempo': 60},
        {'nombre': 'Reparación de pérdida de agua', 'precio': 4000, 'tiempo': 90},
        {'nombre': 'Cambio de grifería', 'precio': 3000, 'tiempo': 60},
        {'nombre': 'Instalación de sanitarios', 'precio': 6000, 'tiempo': 120},
    ],
    'Electricista': [
        {'nombre': 'Revisión de tablero eléctrico', 'precio': 3500, 'tiempo': 60},
        {'nombre': 'Instalación de tomas y llaves', 'precio': 2500, 'tiempo': 60},
        {'nombre': 'Colocación de artefactos de iluminación', 'precio': 3000, 'tiempo': 60},
        {'nombre': 'Reparación de cortocircuito', 'precio': 4500, 'tiempo': 90},
    ],
    'Carpintero': [
        {'nombre': 'Fabricación de mueble a medida', 'precio': 15000, 'tiempo': 480},
        {'nombre': 'Reparación de muebles', 'precio': 4000, 'tiempo': 120},
        {'nombre': 'Colocación de estantes', 'precio': 2500, 'tiempo': 60},
        {'nombre': 'Ajuste de puertas y cajones', 'precio': 2000, 'tiempo': 60},
    ],
    'Pintor': [
        {'nombre': 'Pintura de interiores (por ambiente)', 'precio': 8000, 'tiempo': 300},
        {'nombre': 'Pintura de exteriores', 'precio': 12000, 'tiempo': 480},
        {'nombre': 'Enduido y preparación de paredes', 'precio': 5000, 'tiempo': 240},
        {'nombre': 'Empapelado', 'precio': 6000, 'tiempo': 240},
    ],
    'Albañil': [
        {'nombre': 'Reparación de mampostería', 'precio': 6000, 'tiempo': 240},
        {'nombre': 'Revoque de paredes', 'precio': 7000, 'tiempo': 300},
        {'nombre': 'Contrapiso y carpeta', 'precio': 9000, 'tiempo': 360},
        {'nombre': 'Construcción de muro', 'precio': 15000, 'tiempo': 480},
    ],
    'Gasista': [
        {'nombre': 'Detección de pérdida de gas', 'precio': 4000, 'tiempo': 60},
        {'nombre': 'Instalación de estufa/calefón', 'precio': 7000, 'tiempo': 120},
        {'nombre': 'Prueba de hermeticidad', 'precio': 5000, 'tiempo': 90},
        {'nombre': 'Conexión de cocina', 'precio': 3500, 'tiempo': 60},
    ],
    'Jardinero': [
        {'nombre': 'Corte de césped', 'precio': 2500, 'tiempo': 60},
        {'nombre': 'Poda de arbustos y árboles', 'precio': 4000, 'tiempo': 120},
        {'nombre': 'Mantenimiento mensual de jardín', 'precio': 8000, 'tiempo': 180},
        {'nombre': 'Diseño y plantación', 'precio': 10000, 'tiempo': 240},
    ],
    'Cerrajero': [
        {'nombre': 'Apertura de puerta', 'precio': 4000, 'tiempo': 45},
        {'nombre': 'Cambio de cerradura', 'precio': 3500, 'tiempo': 60},
        {'nombre': 'Copia de llaves', 'precio': 1000, 'tiempo': 15},
        {'nombre': 'Instalación de cerradura de seguridad', 'precio': 6000, 'tiempo': 90},
    ],
    'Técnico en Refrigeración': [
        {'nombre': 'Carga de gas de aire acondicionado', 'precio': 6000, 'tiempo': 90},
        {'nombre': 'Instalación de split', 'precio': 12000, 'tiempo': 180},
        {'nombre': 'Limpieza de aire acondicionado', 'precio': 4000, 'tiempo': 60},
        {'nombre': 'Reparación de heladera', 'precio': 7000, 'tiempo': 120},
    ],
    'Techista': [
        {'nombre': 'Reparación de filtraciones', 'precio': 6000, 'tiempo': 180},
        {'nombre': 'Colocación de membrana', 'precio': 10000, 'tiempo': 300},
        {'nombre': 'Cambio de tejas', 'precio': 8000, 'tiempo': 240},
        {'nombre': 'Impermeabilización de techo', 'precio': 12000, 'tiempo': 360},
    ],
    'Herrero': [
        {'nombre': 'Fabricación de reja', 'precio': 18000, 'tiempo': 480},
        {'nombre': 'Reparación de portón', 'precio': 6000, 'tiempo': 180},
        {'nombre': 'Soldadura de estructura metálica', 'precio': 5000, 'tiempo': 120},
        {'nombre': 'Colocación de reja de seguridad', 'precio': 9000, 'tiempo': 240},
    ],
    'Vidriero': [
        {'nombre': 'Cambio de vidrio', 'precio': 4000, 'tiempo': 60},
        {'nombre': 'Colocación de espejo', 'precio': 3500, 'tiempo': 60},
        {'nombre': 'Instalación de mampara', 'precio': 12000, 'tiempo': 180},
        {'nombre': 'Reparación de cerramiento', 'precio': 5000, 'tiempo': 120},
    ],
    'Fumigador': [
        {'nombre': 'Fumigación de hogar', 'precio': 5000, 'tiempo': 90},
        {'nombre': 'Control de roedores', 'precio': 6000, 'tiempo': 90},
        {'nombre': 'Desinfección de ambientes', 'precio': 7000, 'tiempo': 120},
        {'nombre': 'Control de cucarachas', 'precio': 4500, 'tiempo': 60},
    ],
    'Limpieza': [
        {'nombre': 'Limpieza de hogar por hora', 'precio': 2000, 'tiempo': 60},
        {'nombre': 'Limpieza profunda', 'precio': 8000, 'tiempo': 240},
        {'nombre': 'Limpieza de fin de obra', 'precio': 12000, 'tiempo': 300},
        {'nombre': 'Limpieza de oficinas', 'precio': 6000, 'tiempo': 180},
    ],
    'Mudanzas': [
        {'nombre': 'Mudanza local (medio día)', 'precio': 15000, 'tiempo': 240},
        {'nombre': 'Flete y traslado de muebles', 'precio': 8000, 'tiempo': 120},
        {'nombre': 'Embalaje de pertenencias', 'precio': 5000, 'tiempo': 120},
        {'nombre': 'Desarme y armado de muebles', 'precio': 4000, 'tiempo': 90},
    ],
    'Tapicero': [
        {'nombre': 'Retapizado de sillón', 'precio': 12000, 'tiempo': 300},
        {'nombre': 'Retapizado de sillas (por unidad)', 'precio': 3500, 'tiempo': 90},
        {'nombre': 'Cambio de espuma', 'precio': 5000, 'tiempo': 120},
        {'nombre': 'Reparación de tapizado', 'precio': 4000, 'tiempo': 120},
    ],
    'Parquetista': [
        {'nombre': 'Pulido de piso de madera', 'precio': 9000, 'tiempo': 300},
        {'nombre': 'Plastificado de parquet', 'precio': 11000, 'tiempo': 360},
        {'nombre': 'Colocación de piso de madera', 'precio': 14000, 'tiempo': 480},
        {'nombre': 'Reparación de tablas', 'precio': 5000, 'tiempo': 120},
    ],
    'Colocador de Durlock': [
        {'nombre': 'Colocación de placa de yeso', 'precio': 7000, 'tiempo': 240},
        {'nombre': 'Armado de cielorraso', 'precio': 10000, 'tiempo': 360},
        {'nombre': 'División de ambientes', 'precio': 12000, 'tiempo': 420},
        {'nombre': 'Reparación de durlock', 'precio': 4000, 'tiempo': 120},
    ],
    'Instalador de Pisos': [
        {'nombre': 'Colocación de cerámicos', 'precio': 9000, 'tiempo': 360},
        {'nombre': 'Colocación de porcelanato', 'precio': 11000, 'tiempo': 420},
        {'nombre': 'Colocación de piso flotante', 'precio': 8000, 'tiempo': 300},
        {'nombre': 'Colocación de zócalos', 'precio': 3500, 'tiempo': 120},
    ],
    'Mecánico': [
        {'nombre': 'Cambio de aceite y filtro', 'precio': 5000, 'tiempo': 60},
        {'nombre': 'Revisión general del vehículo', 'precio': 4000, 'tiempo': 90},
        {'nombre': 'Cambio de pastillas de freno', 'precio': 7000, 'tiempo': 120},
        {'nombre': 'Service completo', 'precio': 15000, 'tiempo': 180},
    ],
    'Gomería': [
        {'nombre': 'Cambio de neumático', 'precio': 2000, 'tiempo': 30},
        {'nombre': 'Reparación de pinchadura', 'precio': 1500, 'tiempo': 30},
        {'nombre': 'Alineación y balanceo', 'precio': 4000, 'tiempo': 60},
        {'nombre': 'Rotación de cubiertas', 'precio': 2500, 'tiempo': 45},
    ],
    'Lavadero de Autos': [
        {'nombre': 'Lavado exterior', 'precio': 2000, 'tiempo': 30},
        {'nombre': 'Lavado completo (interior y exterior)', 'precio': 3500, 'tiempo': 60},
        {'nombre': 'Detailing y encerado', 'precio': 8000, 'tiempo': 180},
        {'nombre': 'Limpieza de tapizados', 'precio': 6000, 'tiempo': 120},
    ],
    'Técnico en Computación': [
        {'nombre': 'Formateo e instalación de sistema', 'precio': 4000, 'tiempo': 120},
        {'nombre': 'Limpieza y mantenimiento de PC', 'precio': 3000, 'tiempo': 90},
        {'nombre': 'Reparación de hardware', 'precio': 5000, 'tiempo': 120},
        {'nombre': 'Eliminación de virus', 'precio': 3500, 'tiempo': 90},
    ],
    'Técnico en Celulares': [
        {'nombre': 'Cambio de pantalla', 'precio': 6000, 'tiempo': 90},
        {'nombre': 'Cambio de batería', 'precio': 4000, 'tiempo': 60},
        {'nombre': 'Reparación de pin de carga', 'precio': 3500, 'tiempo': 90},
        {'nombre': 'Liberación de equipo', 'precio': 2500, 'tiempo': 30},
    ],
    'Instalador de Alarmas': [
        {'nombre': 'Instalación de alarma domiciliaria', 'precio': 12000, 'tiempo': 180},
        {'nombre': 'Agregado de sensores', 'precio': 3500, 'tiempo': 60},
        {'nombre': 'Mantenimiento de sistema de alarma', 'precio': 4000, 'tiempo': 90},
        {'nombre': 'Configuración de central', 'precio': 5000, 'tiempo': 90},
    ],
    'Instalador de Cámaras': [
        {'nombre': 'Instalación de cámara de seguridad', 'precio': 6000, 'tiempo': 120},
        {'nombre': 'Instalación de kit de videovigilancia', 'precio': 18000, 'tiempo': 300},
        {'nombre': 'Configuración de acceso remoto', 'precio': 3500, 'tiempo': 60},
        {'nombre': 'Mantenimiento de cámaras', 'precio': 4000, 'tiempo': 90},
    ],
    'Paseador de Perros': [
        {'nombre': 'Paseo individual (1 hora)', 'precio': 2000, 'tiempo': 60},
        {'nombre': 'Paseo grupal', 'precio': 1500, 'tiempo': 60},
        {'nombre': 'Guardería por día', 'precio': 5000, 'tiempo': 480},
        {'nombre': 'Visita a domicilio', 'precio': 1800, 'tiempo': 45},
    ],
    'Veterinario': [
        {'nombre': 'Consulta general', 'precio': 4000, 'tiempo': 30},
        {'nombre': 'Vacunación', 'precio': 3000, 'tiempo': 30},
        {'nombre': 'Desparasitación', 'precio': 2500, 'tiempo': 30},
        {'nombre': 'Atención a domicilio', 'precio': 6000, 'tiempo': 60},
    ],
    'Peluquero Canino': [
        {'nombre': 'Baño y secado', 'precio': 3000, 'tiempo': 60},
        {'nombre': 'Corte de pelo', 'precio': 4500, 'tiempo': 90},
        {'nombre': 'Corte de uñas', 'precio': 1500, 'tiempo': 30},
        {'nombre': 'Baño, corte y estética completa', 'precio': 6000, 'tiempo': 120},
    ],
    'Vendedor@': [
        {'nombre': 'Venta de productos', 'precio': 1000, 'tiempo': 30},
        {'nombre': 'Armado de catálogo', 'precio': 2000, 'tiempo': 60},
        {'nombre': 'Envío a domicilio', 'precio': 1500, 'tiempo': 60},
    ],
    'Instructor de Fitness': [
        {'nombre': 'Entrenamiento personal (sesión)', 'precio': 3000, 'tiempo': 60},
        {'nombre': 'Rutina personalizada', 'precio': 5000, 'tiempo': 60},
        {'nombre': 'Clase grupal', 'precio': 1500, 'tiempo': 60},
        {'nombre': 'Plan mensual de entrenamiento', 'precio': 12000, 'tiempo': 60},
    ],
    'Peluquero': [
        {'nombre': 'Corte de pelo', 'precio': 2500, 'tiempo': 45},
        {'nombre': 'Corte y barba', 'precio': 3500, 'tiempo': 60},
        {'nombre': 'Coloración', 'precio': 6000, 'tiempo': 120},
        {'nombre': 'Peinado', 'precio': 3000, 'tiempo': 60},
    ],
}

# Servicios genéricos para cualquier profesión que no esté mapeada arriba. Así el
# alta nunca queda sin servicios (requisito "sí o sí").
BASE_SERVICIOS_GENERICOS = [
    {'nombre': 'Consulta / presupuesto', 'precio': 0, 'tiempo': 30},
    {'nombre': 'Servicio a domicilio', 'precio': 3000, 'tiempo': 60},
    {'nombre': 'Servicio en taller / local', 'precio': 2500, 'tiempo': 60},
]


def servicios_base_para(profesion_nombre: str):
    """Lista de servicios base (dicts) para una profesión.

    Cae en `BASE_SERVICIOS_GENERICOS` si la profesión no tiene catálogo propio,
    para garantizar que toda cuenta base arranque con al menos un servicio.
    """
    return BASE_SERVICIOS.get(profesion_nombre, BASE_SERVICIOS_GENERICOS)
