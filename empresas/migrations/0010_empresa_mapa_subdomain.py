import re
import unicodedata

from django.db import migrations, models


def _slugify_subdomain(nombre: str) -> str:
    if not nombre:
        return 'empresa'
    s = unicodedata.normalize('NFKD', nombre)
    s = ''.join(c for c in s if not unicodedata.combining(c))
    s = s.lower().strip()
    s = re.sub(r'[^a-z0-9]+', '-', s)
    s = re.sub(r'-+', '-', s).strip('-')
    return (s[:80] or 'empresa')


def populate_subdomains(apps, schema_editor):
    Empresa = apps.get_model('empresas', 'Empresa')
    usados = set(
        Empresa.objects.exclude(subdomain__isnull=True)
        .exclude(subdomain='')
        .values_list('subdomain', flat=True)
    )

    for empresa in Empresa.objects.all().order_by('id'):
        if empresa.subdomain:
            usados.add(empresa.subdomain)
            continue

        base = _slugify_subdomain(empresa.nombre)
        candidate = base
        i = 2
        while candidate in usados:
            candidate = f'{base}-{i}'
            i += 1

        empresa.subdomain = candidate
        empresa.save(update_fields=['subdomain'])
        usados.add(candidate)


ADD_COLUMNS_SQL = """
ALTER TABLE empresa
    ADD COLUMN IF NOT EXISTS compartir_ubicacion_mapa boolean NOT NULL DEFAULT true;
ALTER TABLE empresa
    ADD COLUMN IF NOT EXISTS subdomain varchar(100) NULL;
CREATE UNIQUE INDEX IF NOT EXISTS empresa_subdomain_key ON empresa (subdomain);
"""


class Migration(migrations.Migration):

    dependencies = [
        ('empresas', '0009_producto_modalidad_entrega'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name='empresa',
                    name='compartir_ubicacion_mapa',
                    field=models.BooleanField(
                        default=True,
                        help_text='Si es False, la empresa no aparece en el mapa pero sí en búsquedas y trabajos urgentes.',
                    ),
                ),
                migrations.AddField(
                    model_name='empresa',
                    name='subdomain',
                    field=models.CharField(
                        blank=True,
                        help_text='Subdominio para landing page pública (ej. peluqueria-juan).',
                        max_length=100,
                        null=True,
                        unique=True,
                    ),
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql=ADD_COLUMNS_SQL,
                    reverse_sql=migrations.RunSQL.noop,
                ),
            ],
        ),
        migrations.RunPython(populate_subdomains, migrations.RunPython.noop),
    ]
