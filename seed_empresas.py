"""
seed_empresas.py
Crea 1000 usuarios tipo empresa con productos o servicios, localizaciones en Uruguay.

Uso:
    docker compose cp seed_empresas.py web:/app/seed_empresas.py
    docker compose exec -T web python manage.py shell < seed_empresas.py
"""

import random
from decimal import Decimal
from django.db import transaction

# ── Límites geográficos de Uruguay ───────────────────────────────────────────
UY_LAT_MIN, UY_LAT_MAX = -34.95, -30.08
UY_LNG_MIN, UY_LNG_MAX = -58.44, -53.09

# ── Ciudades reales de Uruguay ────────────────────────────────────────────────
CIUDADES = [
    "Montevideo", "Salto", "Ciudad de la Costa", "Paysandú", "Las Piedras",
    "Rivera", "Maldonado", "Tacuarembó", "Melo", "Mercedes",
    "Artigas", "Minas", "San José de Mayo", "Durazno", "Florida",
    "Treinta y Tres", "Rocha", "Fray Bentos", "Nueva Helvecia", "Colonia del Sacramento",
    "Young", "Trinidad", "Paso de los Toros", "Canelones", "Punta del Este",
]

NOMBRES = [
    "Agustín","Valentina","Santiago","Camila","Mateo","Lucía","Nicolás","Sofía",
    "Facundo","Martina","Tomás","Isabella","Joaquín","Emma","Lucas","Florencia",
    "Maximiliano","Natalia","Andrés","Gabriela","Diego","Paula","Federico","Carolina",
    "Roberto","Verónica","Carlos","Adriana","Jorge","Claudia","Fernando","Patricia",
    "Sebastián","Daniela","Pablo","Silvana","Gonzalo","Mariela","Rodrigo","Cecilia",
    "Alejandro","Marcela","Gustavo","Andrea","Ramiro","Lorena","Cristian","Roxana",
    "Hernán","Laura","Eduardo","Paola","Ignacio","Karina","Leandro","Vanesa",
    "Mauricio","Jimena","Darío","Noelia","Esteban","Romina","Claudio","Graciela",
    "Sergio","Marta","Hugo","Elena","Oscar","Rosa","Daniel","Carmen","Manuel","Teresa",
]

APELLIDOS = [
    "García","Rodríguez","González","Fernández","López","Martínez","Sánchez","Pérez",
    "Gómez","Martín","Jiménez","Ruiz","Hernández","Díaz","Moreno","Álvarez",
    "Muñoz","Romero","Alonso","Gutiérrez","Navarro","Torres","Domínguez","Vásquez",
    "Ramos","Gil","Ramírez","Serrano","Blanco","Suárez","Molina","Morales",
    "Ortega","Delgado","Castro","Ortiz","Rubio","Marín","Sanz","Iglesias",
    "Núñez","Medina","Garrido","Cortés","Castillo","Santos","Lozano","Guerrero",
    "Cano","Prieto","Méndez","Cruz","Calvo","Gallego","Vidal","León",
    "Herrera","Márquez","Peña","Flores","Cabrera","Silva","Rojas","Vargas",
    "Da Silva","Dos Santos","Pereira","Acosta","Benítez","Aguirre","Reyes",
]

PREFIJOS_EMPRESA = [
    "La Casa de","El Taller de","Servicios","Soluciones","Grupo","Studio",
    "Arte y","Diseño","Construye","Repara","Renueva","Cuida","Express","Pro",
]

SUFIJOS_EMPRESA = [
    "del Sur","del Norte","Uruguay","UY","Total","Plus","Max","Fast","24hs",
    "Profesional","Experto","Confiable","Quality","Premium","Master",
]

CATEGORIAS_PRODUCTOS = [
    "Herramientas","Materiales","Repuestos","Insumos","Equipos",
    "Accesorios","Productos de limpieza","Pintura","Electricidad","Plomería",
]

PRODUCTOS_NOMBRES = [
    "Taladro inalámbrico","Sierra circular","Lijadora orbital","Destornillador eléctrico",
    "Nivel láser","Martillo demoledor","Amoladora angular","Soldadora inverter",
    "Compresor de aire","Pistola de calor","Llave de impacto","Rotomartillo",
    "Pintura látex blanca","Pintura esmalte","Rodillo 22cm","Brocha 3 pulgadas",
    "Cinta métrica 5m","Nivel de burbuja","Escuadra 45°","Serrucho manual",
    "Cable eléctrico 2.5mm","Interruptor simple","Toma corriente doble","Caja de paso",
    "Llave Stillson 14\"","Teflon rollo","Codo 3/4\" PVC","Caño 1/2\" 3m",
    "Yeso construcción 5kg","Cemento cola 25kg","Arena gruesa bolsa","Cal hidratada",
    "Cerámica 45x45","Porcelanato 60x60","Adhesivo cerámico","Sellador juntas",
    "Guantes de trabajo","Casco seguridad","Anteojos protectores","Botas punta acero",
    "Escalera aluminio 6 peldaños","Andamio modular","Caballete","Banco de trabajo",
]

# Servicios por profesion_id (1=Electricista, 2=Plomero, 3=Carpintero)
SERVICIOS_POR_PROFESION = {
    1: [
        "Instalación eléctrica completa","Reparación de tablero","Colocación de tomacorrientes",
        "Instalación de luces LED","Revisión de instalación eléctrica","Cambio de llaves y tomas",
        "Instalación de medidor","Puesta a tierra","Instalación de aire acondicionado",
        "Iluminación exterior","Instalación de cámaras","Alarma perimetral",
        "Automatización de portón","Instalación de generador","Reparación urgente eléctrica",
        "Conexión monofásica","Conexión trifásica","Instalación de calefón eléctrico",
        "Mantenimiento preventivo eléctrico","Certificación de instalación",
    ],
    2: [
        "Destape de cañerías","Instalación de baño completo","Cambio de canillas",
        "Reparación de pérdidas","Instalación de termotanque","Colocación de inodoro",
        "Instalación de ducha","Conexión de lavarropas","Limpieza de sifones",
        "Detección de pérdidas ocultas","Instalación de calefón","Cambio de cañerías",
        "Instalación de bomba de agua","Mantenimiento de tanque","Instalación de filtro de agua",
        "Reparación de cisterna","Conexión de lavavajillas","Instalación de bañera",
        "Trabajo en azotea","Reparación urgente plomería",
    ],
    3: [
        "Fabricación de muebles a medida","Reparación de muebles","Instalación de puertas",
        "Colocación de pisos de madera","Fabricación de placard","Restauración de muebles",
        "Instalación de ventanas de madera","Fabricación de escalera","Deck de madera",
        "Pergola de madera","Estanterías a medida","Reparación de marcos",
        "Barnizado y lustrado","Fabricación de cocina a medida","Instalación de molduras",
        "Reparación de pisos flotantes","Colocación de zócalos","Fabricación de mesa",
        "Fabricación de sillas","Mantenimiento de muebles de jardín",
    ],
}

TIEMPOS_POSIBLES = [30, 45, 60, 90, 120, 180, 240, 300, 360, 480]


def rand_lat():
    return round(random.uniform(UY_LAT_MIN, UY_LAT_MAX), 7)

def rand_lng():
    return round(random.uniform(UY_LNG_MIN, UY_LNG_MAX), 7)

def rand_precio(min_val=500, max_val=15000):
    return Decimal(str(round(random.uniform(min_val, max_val), 2)))

def rand_email(nombre, apellido, idx):
    dominio = random.choice(["gmail.com","hotmail.com","yahoo.com","outlook.com","live.com"])
    base = (
        f"{nombre.lower().replace(' ','')}.{apellido.lower().replace(' ','')}"
        .replace("á","a").replace("é","e").replace("í","i")
        .replace("ó","o").replace("ú","u").replace("ñ","n")
    )
    return f"{base}{idx}@{dominio}"

def rand_telefono():
    return f"09{random.randint(1000000, 9999999)}"

def rand_nombre_empresa(nombre, apellido):
    r = random.random()
    if r < 0.35:
        return f"{random.choice(PREFIJOS_EMPRESA)} {nombre}"
    elif r < 0.65:
        return f"{nombre} {apellido} {random.choice(SUFIJOS_EMPRESA)}"
    else:
        return f"{random.choice(PREFIJOS_EMPRESA)} {apellido}"


def run():
    from usuario.models import Usuario
    from localizacion.models import Localizacion
    from usuario_localizacion.models import UsuarioLocalizacion
    from usuario_profesion.models import UsuarioProfesion
    from profesion.models import Profesion
    from empresas.models import Empresa, CategoriaProducto, Producto
    from servicios.models import Servicio

    profesiones = {p.id: p for p in Profesion.objects.filter(id__in=[1, 2, 3])}
    if not profesiones:
        print("❌ No hay profesiones con id 1-3. Abortando.")
        return
    print(f"✅ Profesiones encontradas: {[f'{p.id}-{p.nombre}' for p in profesiones.values()]}")

    profesion_ids_disponibles = list(profesiones.keys())

    TOTAL = 1000
    creados = 0
    errores = 0

    print(f"🚀 Iniciando seed de {TOTAL} usuarios empresa...")

    for i in range(TOTAL):
        nombre   = random.choice(NOMBRES)
        apellido = random.choice(APELLIDOS)
        email    = rand_email(nombre, apellido, i)
        telefono = rand_telefono()
        ciudad   = random.choice(CIUDADES)
        lat      = rand_lat()
        lng      = rand_lng()
        tipo_empresa = random.choice(["productos", "servicios"])

        n_profesiones = random.randint(1, min(3, len(profesion_ids_disponibles)))
        prof_ids_elegidas = random.sample(profesion_ids_disponibles, n_profesiones)

        try:
            with transaction.atomic():
                # 1. Usuario
                trabajo_domicilio = random.choice([True, False])
                trabajo_local     = random.choice([True, False])
                if not trabajo_domicilio and not trabajo_local:
                    trabajo_domicilio = True

                usuario = Usuario.objects.create_user(
                    correo=email,
                    password="Seed1234!",
                    nombre=nombre,
                    apellido=apellido,
                    telefono=telefono,
                    trabajo_domicilio=trabajo_domicilio,
                    trabajo_local=trabajo_local,
                    is_owner_empresa=True,
                    foto_url="",
                    rounded_foto_url="",
                )

                # 2. Localizacion
                localizacion = Localizacion.objects.create(
                    ubicacion=f"{ciudad}, Uruguay",
                    latitud=lat,
                    longitud=lng,
                    address=f"{ciudad}, Uruguay",
                    city=ciudad,
                    country="Uruguay",
                    county="",
                    state="",
                    isPrimary=True,
                )

                # 3. UsuarioLocalizacion
                UsuarioLocalizacion.objects.create(
                    usuario=usuario,
                    localizacion=localizacion,
                    es_principal=True,
                )

                # 4. Profesiones
                for pid in prof_ids_elegidas:
                    UsuarioProfesion.objects.create(
                        usuario=usuario,
                        profesion=profesiones[pid],
                    )

                # 5. Empresa
                empresa = Empresa.objects.create(
                    nombre=rand_nombre_empresa(nombre, apellido),
                    ubicacion=f"{ciudad}, Uruguay",
                    descripcion=f"Empresa de {tipo_empresa} en {ciudad}.",
                    latitud=lat,
                    longitud=lng,
                    admin_id=usuario,
                    localizacion=localizacion,
                    unipersonal=True,
                    pais="UY",
                    vende_productos=(tipo_empresa == "productos"),
                    vende_servicios=(tipo_empresa == "servicios"),
                    acepta_efectivo=random.choice([True, False]),
                    acepta_tarjeta=False,
                    is_mercadopago_vinculado=False,
                    currency="UYU",
                )

                # 6a. Productos
                if tipo_empresa == "productos":
                    n_productos  = random.randint(1, 20)
                    cat_nombre   = random.choice(CATEGORIAS_PRODUCTOS)
                    categoria    = CategoriaProducto.objects.create(
                        nombre=cat_nombre,
                        empresa=empresa,
                    )
                    nombres_usados = set()
                    for j in range(n_productos):
                        prod_nombre = random.choice(PRODUCTOS_NOMBRES)
                        if prod_nombre in nombres_usados:
                            prod_nombre = f"{prod_nombre} v{j}"
                        nombres_usados.add(prod_nombre)
                        Producto.objects.create(
                            nombre=prod_nombre,
                            descripcion=f"Producto: {prod_nombre}",
                            precio=rand_precio(200, 20000),
                            empresa=empresa,
                            categoria=categoria,
                            codigo=f"COD{i:04d}{j:02d}",
                        )

                # 6b. Servicios
                else:
                    n_servicios = random.randint(1, 20)
                    servicios_creados = set()
                    intentos = 0
                    while len(servicios_creados) < n_servicios and intentos < 200:
                        intentos += 1
                        pid = random.choice(prof_ids_elegidas)
                        candidatos = SERVICIOS_POR_PROFESION.get(pid, [])
                        if not candidatos:
                            continue
                        svc_nombre = random.choice(candidatos)
                        clave = (pid, svc_nombre)
                        if clave in servicios_creados:
                            continue
                        servicios_creados.add(clave)
                        Servicio.objects.create(
                            usuario=usuario,
                            profesion=profesiones[pid],
                            nombre=svc_nombre,
                            precio=rand_precio(500, 10000),
                            divisa="UYU",
                            tiempo=random.choice(TIEMPOS_POSIBLES),
                        )

                creados += 1
                if creados % 100 == 0:
                    print(f"  ✅ {creados}/{TOTAL} usuarios creados...")

        except Exception as e:
            errores += 1
            print(f"  ❌ Error en usuario {i} ({email}): {e}")
            if errores > 50:
                print("Demasiados errores, abortando.")
                break

    print(f"\n🎉 Seed finalizado: {creados} usuarios creados, {errores} errores.")


run()