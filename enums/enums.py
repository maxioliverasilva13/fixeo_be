CURRENCY_CHOICES = [
    ('ARS', 'Peso Argentino'),
    ('BRL', 'Real Brasileño'),
    ('CLP', 'Peso Chileno'),
    ('COP', 'Peso Colombiano'),
    ('MXN', 'Peso Mexicano'),
    ('PEN', 'Sol Peruano'),
    ('UYU', 'Peso Uruguayo'),
    ('BOB', 'Boliviano'),
    ('PYG', 'Guaraní Paraguayo'),
    ('VES', 'Bolívar Venezolano'),
    ('CRC', 'Colón Costarricense'),
    ('DOP', 'Peso Dominicano'),
    ('GTQ', 'Quetzal Guatemalteco'),
    ('HNL', 'Lempira Hondureño'),
    ('NIO', 'Córdoba Nicaragüense'),
    ('PAB', 'Balboa Panameño'),
    ('USD', 'Dólar Estadounidense'),
]

PAIS_CHOICES = [
    ('AR', 'Argentina'),
    ('BO', 'Bolivia'),
    ('BR', 'Brasil'),
    ('CL', 'Chile'),
    ('CO', 'Colombia'),
    ('CR', 'Costa Rica'),
    ('CU', 'Cuba'),
    ('DO', 'República Dominicana'),
    ('EC', 'Ecuador'),
    ('GT', 'Guatemala'),
    ('HN', 'Honduras'),
    ('MX', 'México'),
    ('NI', 'Nicaragua'),
    ('PA', 'Panamá'),
    ('PE', 'Perú'),
    ('PR', 'Puerto Rico'),
    ('PY', 'Paraguay'),
    ('SV', 'El Salvador'),
    ('UY', 'Uruguay'),
    ('VE', 'Venezuela'),
]

PAIS_TO_CURRENCY = {
    'AR': 'ARS',
    'BO': 'BOB',
    'BR': 'BRL',
    'CL': 'CLP',
    'CO': 'COP',
    'CR': 'CRC',
    'CU': 'USD',
    'DO': 'DOP',
    'EC': 'USD',
    'GT': 'GTQ',
    'HN': 'HNL',
    'MX': 'MXN',
    'NI': 'NIO',
    'PA': 'PAB',
    'PE': 'PEN',
    'PR': 'USD',
    'PY': 'PYG',
    'SV': 'USD',
    'UY': 'UYU',
    'VE': 'VES',
}


def moneda_local_desde_pais(pais: str) -> str:
    if not pais:
        return 'USD'
    return PAIS_TO_CURRENCY.get(str(pais).upper(), 'USD')


def divisas_permitidas_para_pais(pais: str) -> list[str]:
    local = moneda_local_desde_pais(pais)
    if local == 'USD':
        return ['USD']
    return ['USD', local]
