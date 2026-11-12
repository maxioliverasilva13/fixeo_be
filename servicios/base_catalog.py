"""
Catálogo de servicios, horarios y fotos "base" por profesión.

Lo usa el endpoint de alta masiva `POST /api/usuarios/registro-base/` (ver
`usuario/views.py::UsuarioViewSet.registro_base`) para que toda cuenta de
profesional creada automáticamente desde la web de prospección arranque, sí o
sí, con servicios realistas, una grilla de horarios y una foto.

Es la única fuente del catálogo base (vive acá, en fixeo_be).

Convenciones:
- `precio` en pesos uruguayos (`BASE_DIVISA = 'UYU'`). Son precios de referencia
  plausibles para Uruguay; se ajustan luego desde la cuenta.
- `tiempo` en minutos (campo `Servicio.tiempo`).
- Las claves de `BASE_SERVICIOS` / `BASE_FOTOS` son el `nombre` EXACTO de la
  profesión en la tabla `profesion` (incluye tildes y símbolos como "Vendedor@").
- Cada servicio puede traer un `foto` propio; si no, se usa la foto de la
  profesión (`foto_base_para`). Las fotos son los íconos del bucket de fixeo
  (activos propios y estables), temáticos por profesión.
"""

BASE_DIVISA = 'UYU'

_ICONS = (
    'https://dibvhmpmocsmqvlemcqk.supabase.co/storage/v1/object/public/'
    'bucketFixea/iconsProfesiones'
)

# Foto por profesión (ícono del bucket). Default para todos los servicios de esa
# profesión salvo que el servicio defina su propio `foto`.
BASE_FOTOS = {
    'Plomero': f'{_ICONS}/plumbing.png',
    'Electricista': f'{_ICONS}/bolt%20(1).png',
    'Carpintero': f'{_ICONS}/saw.png',
    'Pintor': f'{_ICONS}/paint-roller.png',
    'Albañil': f'{_ICONS}/building-materials.png',
    'Gasista': f'{_ICONS}/plumbing.png',
    'Jardinero': f'{_ICONS}/daisy-alt.png',
    'Cerrajero': f'{_ICONS}/key.png',
    'Técnico en Refrigeración': f'{_ICONS}/air-conditioner.png',
    'Techista': f'{_ICONS}/roof.png',
    'Herrero': f'{_ICONS}/rock-hammer.png',
    'Vidriero': f'{_ICONS}/house-window.png',
    'Fumigador': f'{_ICONS}/spray-can.png',
    'Limpieza': f'{_ICONS}/broom.png',
    'Mudanzas': f'{_ICONS}/box-open.png',
    'Tapicero': f'{_ICONS}/loveseat.png',
    'Parquetista': f'{_ICONS}/floor-layer.png',
    'Colocador de Durlock': f'{_ICONS}/floor-layer.png',
    'Instalador de Pisos': f'{_ICONS}/floor-layer.png',
    'Mecánico': f'{_ICONS}/car-mechanic.png',
    'Gomería': f'{_ICONS}/tire.png',
    'Lavadero de Autos': f'{_ICONS}/car-wash.png',
    'Técnico en Computación': f'{_ICONS}/computer.png',
    'Técnico en Celulares': f'{_ICONS}/smartphone.png',
    'Instalador de Alarmas': f'{_ICONS}/camera-cctv.png',
    'Instalador de Cámaras': f'{_ICONS}/camera-cctv.png',
    'Paseador de Perros': f'{_ICONS}/paw-heart.png',
    'Veterinario': f'{_ICONS}/paw-heart.png',
    'Peluquero Canino': f'{_ICONS}/barber-shop.png',
    'Peluquero': f'{_ICONS}/barber-shop.png',
    'Instructor de Fitness': f'{_ICONS}/gym.png',
    'Manicura': f'{_ICONS}/barber-shop.png',
    'Lavandería': f'{_ICONS}/broom.png',
    'Vendedor@': f'{_ICONS}/box-open.png',
}

FOTO_GENERICA = f'{_ICONS}/box-open.png'

# Grilla horaria por defecto para la empresa unipersonal del profesional base.
# `dia_semana` usa el nombre en inglés en minúsculas, igual que
# `Empresa.esta_abierta_ahora` (ver empresas/models.py), que compara contra
# `datetime.strftime('%A').lower()`.
BASE_HORARIOS = [
    {'dia_semana': 'monday', 'hora_inicio': '08:00', 'hora_fin': '18:00'},
    {'dia_semana': 'tuesday', 'hora_inicio': '08:00', 'hora_fin': '18:00'},
    {'dia_semana': 'wednesday', 'hora_inicio': '08:00', 'hora_fin': '18:00'},
    {'dia_semana': 'thursday', 'hora_inicio': '08:00', 'hora_fin': '18:00'},
    {'dia_semana': 'friday', 'hora_inicio': '08:00', 'hora_fin': '18:00'},
    {'dia_semana': 'saturday', 'hora_inicio': '08:00', 'hora_fin': '13:00'},
]

# Servicios base por profesión. Precios de referencia en UYU (Uruguay).
BASE_SERVICIOS = {
    'Plomero': [
        {'nombre': 'Visita y diagnóstico', 'precio': 800, 'tiempo': 30},
        {'nombre': 'Destape de cañería', 'precio': 2200, 'tiempo': 60},
        {'nombre': 'Reparación de pérdida de agua', 'precio': 2600, 'tiempo': 90},
        {'nombre': 'Cambio de grifería', 'precio': 1800, 'tiempo': 60},
        {'nombre': 'Cambio de flexible o canilla', 'precio': 1200, 'tiempo': 45},
        {'nombre': 'Instalación de sanitario / inodoro', 'precio': 3500, 'tiempo': 120},
        {'nombre': 'Instalación de calefón', 'precio': 4000, 'tiempo': 150},
    ],
    'Electricista': [
        {'nombre': 'Visita y diagnóstico', 'precio': 800, 'tiempo': 30},
        {'nombre': 'Revisión de tablero eléctrico', 'precio': 2000, 'tiempo': 60},
        {'nombre': 'Instalación de tomas y llaves', 'precio': 1400, 'tiempo': 60},
        {'nombre': 'Colocación de artefactos de luz', 'precio': 1600, 'tiempo': 60},
        {'nombre': 'Reparación de cortocircuito', 'precio': 2800, 'tiempo': 90},
        {'nombre': 'Instalación eléctrica por ambiente', 'precio': 4500, 'tiempo': 180},
        {'nombre': 'Colocación de disyuntor / térmica', 'precio': 2200, 'tiempo': 60},
    ],
    'Carpintero': [
        {'nombre': 'Visita y presupuesto', 'precio': 700, 'tiempo': 30},
        {'nombre': 'Reparación de muebles', 'precio': 2500, 'tiempo': 120},
        {'nombre': 'Colocación de estantes', 'precio': 1500, 'tiempo': 60},
        {'nombre': 'Ajuste de puertas y cajones', 'precio': 1300, 'tiempo': 60},
        {'nombre': 'Fabricación de mueble a medida', 'precio': 12000, 'tiempo': 480},
        {'nombre': 'Colocación de placard', 'precio': 7000, 'tiempo': 300},
    ],
    'Pintor': [
        {'nombre': 'Visita y presupuesto', 'precio': 700, 'tiempo': 30},
        {'nombre': 'Pintura de ambiente (hasta 20 m²)', 'precio': 5500, 'tiempo': 300},
        {'nombre': 'Pintura de exteriores (m²)', 'precio': 450, 'tiempo': 60},
        {'nombre': 'Enduido y preparación de paredes', 'precio': 3500, 'tiempo': 240},
        {'nombre': 'Pintura de aberturas y rejas', 'precio': 2500, 'tiempo': 180},
        {'nombre': 'Impermeabilización de pared húmeda', 'precio': 4000, 'tiempo': 240},
    ],
    'Albañil': [
        {'nombre': 'Visita y presupuesto', 'precio': 800, 'tiempo': 30},
        {'nombre': 'Reparación de mampostería', 'precio': 4000, 'tiempo': 240},
        {'nombre': 'Revoque de paredes (m²)', 'precio': 600, 'tiempo': 60},
        {'nombre': 'Contrapiso y carpeta (m²)', 'precio': 700, 'tiempo': 90},
        {'nombre': 'Construcción de muro', 'precio': 12000, 'tiempo': 480},
        {'nombre': 'Colocación de cerámica (m²)', 'precio': 800, 'tiempo': 90},
    ],
    'Gasista': [
        {'nombre': 'Visita y diagnóstico', 'precio': 900, 'tiempo': 30},
        {'nombre': 'Detección de pérdida de gas', 'precio': 2500, 'tiempo': 60},
        {'nombre': 'Instalación de estufa / calefón', 'precio': 3500, 'tiempo': 120},
        {'nombre': 'Prueba de hermeticidad', 'precio': 2800, 'tiempo': 90},
        {'nombre': 'Conexión de cocina', 'precio': 2000, 'tiempo': 60},
        {'nombre': 'Cambio de regulador / garrafa', 'precio': 1200, 'tiempo': 45},
    ],
    'Jardinero': [
        {'nombre': 'Corte de césped', 'precio': 1500, 'tiempo': 60},
        {'nombre': 'Poda de arbustos y árboles', 'precio': 2500, 'tiempo': 120},
        {'nombre': 'Mantenimiento mensual de jardín', 'precio': 5000, 'tiempo': 180},
        {'nombre': 'Limpieza de terreno / desmalezado', 'precio': 3500, 'tiempo': 180},
        {'nombre': 'Diseño y plantación', 'precio': 6000, 'tiempo': 240},
        {'nombre': 'Colocación de césped / tepes', 'precio': 7000, 'tiempo': 300},
    ],
    'Cerrajero': [
        {'nombre': 'Apertura de puerta', 'precio': 2000, 'tiempo': 45},
        {'nombre': 'Cambio de cerradura', 'precio': 2200, 'tiempo': 60},
        {'nombre': 'Copia de llaves', 'precio': 400, 'tiempo': 15},
        {'nombre': 'Instalación de cerradura de seguridad', 'precio': 3500, 'tiempo': 90},
        {'nombre': 'Apertura de auto', 'precio': 2500, 'tiempo': 45},
        {'nombre': 'Reparación de cerradura', 'precio': 1800, 'tiempo': 60},
    ],
    'Técnico en Refrigeración': [
        {'nombre': 'Visita y diagnóstico', 'precio': 900, 'tiempo': 30},
        {'nombre': 'Carga de gas de aire acondicionado', 'precio': 3500, 'tiempo': 90},
        {'nombre': 'Instalación de split', 'precio': 6500, 'tiempo': 180},
        {'nombre': 'Limpieza de aire acondicionado', 'precio': 2200, 'tiempo': 60},
        {'nombre': 'Reparación de heladera', 'precio': 3500, 'tiempo': 120},
        {'nombre': 'Desinstalación / traslado de split', 'precio': 3000, 'tiempo': 120},
    ],
    'Techista': [
        {'nombre': 'Visita y presupuesto', 'precio': 800, 'tiempo': 30},
        {'nombre': 'Reparación de filtraciones', 'precio': 4000, 'tiempo': 180},
        {'nombre': 'Colocación de membrana (m²)', 'precio': 650, 'tiempo': 60},
        {'nombre': 'Cambio de tejas / chapas', 'precio': 5000, 'tiempo': 240},
        {'nombre': 'Impermeabilización de techo', 'precio': 7000, 'tiempo': 300},
        {'nombre': 'Limpieza de canaletas', 'precio': 2500, 'tiempo': 120},
    ],
    'Herrero': [
        {'nombre': 'Visita y presupuesto', 'precio': 800, 'tiempo': 30},
        {'nombre': 'Reparación de portón', 'precio': 4000, 'tiempo': 180},
        {'nombre': 'Soldadura de estructura metálica', 'precio': 3000, 'tiempo': 120},
        {'nombre': 'Fabricación de reja a medida', 'precio': 14000, 'tiempo': 480},
        {'nombre': 'Colocación de reja de seguridad', 'precio': 6000, 'tiempo': 240},
        {'nombre': 'Automatización de portón', 'precio': 9000, 'tiempo': 300},
    ],
    'Vidriero': [
        {'nombre': 'Visita y presupuesto', 'precio': 700, 'tiempo': 30},
        {'nombre': 'Cambio de vidrio', 'precio': 2500, 'tiempo': 60},
        {'nombre': 'Colocación de espejo', 'precio': 2200, 'tiempo': 60},
        {'nombre': 'Instalación de mampara de baño', 'precio': 7000, 'tiempo': 180},
        {'nombre': 'Reparación de cerramiento de aluminio', 'precio': 3000, 'tiempo': 120},
        {'nombre': 'Colocación de blindex', 'precio': 9000, 'tiempo': 240},
    ],
    'Fumigador': [
        {'nombre': 'Fumigación de hogar', 'precio': 2800, 'tiempo': 90},
        {'nombre': 'Control de roedores', 'precio': 3200, 'tiempo': 90},
        {'nombre': 'Desinfección de ambientes', 'precio': 3500, 'tiempo': 120},
        {'nombre': 'Control de cucarachas y hormigas', 'precio': 2500, 'tiempo': 60},
        {'nombre': 'Control de pulgas y garrapatas', 'precio': 3000, 'tiempo': 90},
    ],
    'Limpieza': [
        {'nombre': 'Limpieza por hora', 'precio': 600, 'tiempo': 60},
        {'nombre': 'Limpieza profunda de hogar', 'precio': 4000, 'tiempo': 240},
        {'nombre': 'Limpieza de fin de obra', 'precio': 6500, 'tiempo': 300},
        {'nombre': 'Limpieza de oficinas', 'precio': 3500, 'tiempo': 180},
        {'nombre': 'Limpieza de vidrios y ventanales', 'precio': 2500, 'tiempo': 120},
        {'nombre': 'Limpieza de tapizados y alfombras', 'precio': 3000, 'tiempo': 120},
    ],
    'Mudanzas': [
        {'nombre': 'Mudanza local (medio día)', 'precio': 9000, 'tiempo': 240},
        {'nombre': 'Flete y traslado de muebles', 'precio': 4500, 'tiempo': 120},
        {'nombre': 'Embalaje de pertenencias', 'precio': 3000, 'tiempo': 120},
        {'nombre': 'Desarme y armado de muebles', 'precio': 2500, 'tiempo': 90},
        {'nombre': 'Mudanza con personal extra', 'precio': 13000, 'tiempo': 360},
    ],
    'Tapicero': [
        {'nombre': 'Visita y presupuesto', 'precio': 700, 'tiempo': 30},
        {'nombre': 'Retapizado de sillón 3 cuerpos', 'precio': 9000, 'tiempo': 300},
        {'nombre': 'Retapizado de silla (por unidad)', 'precio': 2200, 'tiempo': 90},
        {'nombre': 'Cambio de espuma', 'precio': 3500, 'tiempo': 120},
        {'nombre': 'Reparación de tapizado', 'precio': 2800, 'tiempo': 120},
    ],
    'Parquetista': [
        {'nombre': 'Visita y presupuesto', 'precio': 800, 'tiempo': 30},
        {'nombre': 'Pulido de piso de madera (m²)', 'precio': 550, 'tiempo': 60},
        {'nombre': 'Plastificado de parquet (m²)', 'precio': 650, 'tiempo': 60},
        {'nombre': 'Colocación de piso de madera (m²)', 'precio': 900, 'tiempo': 90},
        {'nombre': 'Reparación de tablas', 'precio': 3000, 'tiempo': 120},
    ],
    'Colocador de Durlock': [
        {'nombre': 'Visita y presupuesto', 'precio': 800, 'tiempo': 30},
        {'nombre': 'Colocación de placa de yeso (m²)', 'precio': 700, 'tiempo': 60},
        {'nombre': 'Armado de cielorraso (m²)', 'precio': 850, 'tiempo': 90},
        {'nombre': 'División de ambientes', 'precio': 8000, 'tiempo': 420},
        {'nombre': 'Reparación de durlock', 'precio': 2500, 'tiempo': 120},
    ],
    'Instalador de Pisos': [
        {'nombre': 'Visita y presupuesto', 'precio': 800, 'tiempo': 30},
        {'nombre': 'Colocación de cerámica (m²)', 'precio': 800, 'tiempo': 90},
        {'nombre': 'Colocación de porcelanato (m²)', 'precio': 950, 'tiempo': 90},
        {'nombre': 'Colocación de piso flotante (m²)', 'precio': 600, 'tiempo': 60},
        {'nombre': 'Colocación de zócalos', 'precio': 2200, 'tiempo': 120},
    ],
    'Mecánico': [
        {'nombre': 'Diagnóstico con scanner', 'precio': 1200, 'tiempo': 45},
        {'nombre': 'Cambio de aceite y filtro', 'precio': 2800, 'tiempo': 60},
        {'nombre': 'Revisión general del vehículo', 'precio': 1500, 'tiempo': 90},
        {'nombre': 'Cambio de pastillas de freno', 'precio': 3500, 'tiempo': 120},
        {'nombre': 'Cambio de correa de distribución', 'precio': 7000, 'tiempo': 240},
        {'nombre': 'Service completo', 'precio': 6500, 'tiempo': 180},
        {'nombre': 'Cambio de batería', 'precio': 1500, 'tiempo': 30},
    ],
    'Gomería': [
        {'nombre': 'Cambio de neumático (por unidad)', 'precio': 500, 'tiempo': 30},
        {'nombre': 'Reparación de pinchadura', 'precio': 600, 'tiempo': 30},
        {'nombre': 'Alineación y balanceo', 'precio': 2200, 'tiempo': 60},
        {'nombre': 'Rotación de cubiertas', 'precio': 900, 'tiempo': 45},
        {'nombre': 'Auxilio y cambio de rueda', 'precio': 1500, 'tiempo': 45},
    ],
    'Lavadero de Autos': [
        {'nombre': 'Lavado exterior', 'precio': 600, 'tiempo': 30},
        {'nombre': 'Lavado completo (interior y exterior)', 'precio': 1100, 'tiempo': 60},
        {'nombre': 'Detailing y encerado', 'precio': 4500, 'tiempo': 180},
        {'nombre': 'Limpieza de tapizados', 'precio': 2800, 'tiempo': 120},
        {'nombre': 'Pulido de ópticas', 'precio': 1500, 'tiempo': 60},
    ],
    'Técnico en Computación': [
        {'nombre': 'Diagnóstico', 'precio': 700, 'tiempo': 30},
        {'nombre': 'Formateo e instalación de sistema', 'precio': 2000, 'tiempo': 120},
        {'nombre': 'Limpieza y mantenimiento de PC', 'precio': 1500, 'tiempo': 90},
        {'nombre': 'Reparación de hardware', 'precio': 2500, 'tiempo': 120},
        {'nombre': 'Eliminación de virus', 'precio': 1800, 'tiempo': 90},
        {'nombre': 'Instalación de red / WiFi', 'precio': 2200, 'tiempo': 90},
    ],
    'Técnico en Celulares': [
        {'nombre': 'Diagnóstico', 'precio': 500, 'tiempo': 20},
        {'nombre': 'Cambio de pantalla', 'precio': 3500, 'tiempo': 90},
        {'nombre': 'Cambio de batería', 'precio': 1800, 'tiempo': 60},
        {'nombre': 'Reparación de pin de carga', 'precio': 2000, 'tiempo': 90},
        {'nombre': 'Liberación de equipo', 'precio': 1200, 'tiempo': 30},
        {'nombre': 'Cambio de glass / vidrio', 'precio': 1500, 'tiempo': 60},
    ],
    'Instalador de Alarmas': [
        {'nombre': 'Visita y presupuesto', 'precio': 700, 'tiempo': 30},
        {'nombre': 'Instalación de alarma domiciliaria', 'precio': 7000, 'tiempo': 180},
        {'nombre': 'Agregado de sensores', 'precio': 2000, 'tiempo': 60},
        {'nombre': 'Mantenimiento de sistema de alarma', 'precio': 2200, 'tiempo': 90},
        {'nombre': 'Configuración de central y app', 'precio': 2800, 'tiempo': 90},
    ],
    'Instalador de Cámaras': [
        {'nombre': 'Visita y presupuesto', 'precio': 700, 'tiempo': 30},
        {'nombre': 'Instalación de cámara de seguridad', 'precio': 3500, 'tiempo': 120},
        {'nombre': 'Instalación de kit de videovigilancia', 'precio': 11000, 'tiempo': 300},
        {'nombre': 'Configuración de acceso remoto', 'precio': 2000, 'tiempo': 60},
        {'nombre': 'Mantenimiento de cámaras', 'precio': 2200, 'tiempo': 90},
    ],
    'Paseador de Perros': [
        {'nombre': 'Paseo individual (1 hora)', 'precio': 700, 'tiempo': 60},
        {'nombre': 'Paseo grupal', 'precio': 500, 'tiempo': 60},
        {'nombre': 'Guardería por día', 'precio': 1800, 'tiempo': 480},
        {'nombre': 'Visita y cuidado a domicilio', 'precio': 900, 'tiempo': 45},
    ],
    'Veterinario': [
        {'nombre': 'Consulta general', 'precio': 1500, 'tiempo': 30},
        {'nombre': 'Vacunación', 'precio': 1200, 'tiempo': 30},
        {'nombre': 'Desparasitación', 'precio': 900, 'tiempo': 30},
        {'nombre': 'Atención a domicilio', 'precio': 2500, 'tiempo': 60},
        {'nombre': 'Control y chequeo', 'precio': 1300, 'tiempo': 30},
    ],
    'Peluquero Canino': [
        {'nombre': 'Baño y secado', 'precio': 1200, 'tiempo': 60},
        {'nombre': 'Corte de pelo', 'precio': 1800, 'tiempo': 90},
        {'nombre': 'Corte de uñas', 'precio': 600, 'tiempo': 30},
        {'nombre': 'Baño, corte y estética completa', 'precio': 2500, 'tiempo': 120},
        {'nombre': 'Deslanado', 'precio': 2000, 'tiempo': 90},
    ],
    'Peluquero': [
        {'nombre': 'Corte de pelo', 'precio': 700, 'tiempo': 45},
        {'nombre': 'Corte y barba', 'precio': 950, 'tiempo': 60},
        {'nombre': 'Coloración', 'precio': 2500, 'tiempo': 120},
        {'nombre': 'Brushing / peinado', 'precio': 900, 'tiempo': 60},
        {'nombre': 'Mechas / reflejos', 'precio': 3500, 'tiempo': 150},
        {'nombre': 'Tratamiento capilar', 'precio': 1500, 'tiempo': 60},
    ],
    'Instructor de Fitness': [
        {'nombre': 'Clase de prueba', 'precio': 0, 'tiempo': 60},
        {'nombre': 'Entrenamiento personal (sesión)', 'precio': 1200, 'tiempo': 60},
        {'nombre': 'Rutina personalizada', 'precio': 2000, 'tiempo': 60},
        {'nombre': 'Clase grupal', 'precio': 600, 'tiempo': 60},
        {'nombre': 'Plan mensual de entrenamiento', 'precio': 4500, 'tiempo': 60},
    ],
    'Manicura': [
        {'nombre': 'Manicura tradicional', 'precio': 800, 'tiempo': 45},
        {'nombre': 'Esmaltado semipermanente', 'precio': 1200, 'tiempo': 60},
        {'nombre': 'Uñas esculpidas / soft gel', 'precio': 2200, 'tiempo': 120},
        {'nombre': 'Pedicura', 'precio': 1100, 'tiempo': 60},
        {'nombre': 'Retiro de esmaltado / capping', 'precio': 500, 'tiempo': 30},
    ],
    'Lavandería': [
        {'nombre': 'Lavado y secado por kilo', 'precio': 250, 'tiempo': 90},
        {'nombre': 'Lavado, secado y planchado', 'precio': 400, 'tiempo': 120},
        {'nombre': 'Lavado de acolchado / frazada', 'precio': 900, 'tiempo': 120},
        {'nombre': 'Lavado de prendas delicadas', 'precio': 600, 'tiempo': 90},
        {'nombre': 'Servicio de retiro y entrega', 'precio': 300, 'tiempo': 30},
    ],
    'Vendedor@': [
        {'nombre': 'Venta de productos', 'precio': 500, 'tiempo': 30},
        {'nombre': 'Armado de catálogo', 'precio': 1000, 'tiempo': 60},
        {'nombre': 'Envío a domicilio', 'precio': 400, 'tiempo': 45},
    ],
}

# Servicios genéricos para cualquier profesión que no esté mapeada arriba. Así el
# alta nunca queda sin servicios (requisito "sí o sí").
BASE_SERVICIOS_GENERICOS = [
    {'nombre': 'Consulta / presupuesto', 'precio': 0, 'tiempo': 30},
    {'nombre': 'Servicio a domicilio', 'precio': 1500, 'tiempo': 60},
    {'nombre': 'Servicio en taller / local', 'precio': 1200, 'tiempo': 60},
]


def servicios_base_para(profesion_nombre: str):
    """Lista de servicios base (dicts) para una profesión.

    Cae en `BASE_SERVICIOS_GENERICOS` si la profesión no tiene catálogo propio,
    para garantizar que toda cuenta base arranque con al menos un servicio.
    """
    return BASE_SERVICIOS.get(profesion_nombre, BASE_SERVICIOS_GENERICOS)


def foto_base_para(profesion_nombre: str) -> str:
    """Foto por defecto (URL) para los servicios de una profesión."""
    return BASE_FOTOS.get(profesion_nombre, FOTO_GENERICA)
