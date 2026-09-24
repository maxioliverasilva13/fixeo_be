from django.db import migrations


def _extremo(servicio, attr):
    """Un servicio de precio fijo aporta su precio a los dos extremos del rango."""
    if servicio.precio_min is not None and servicio.precio_max is not None:
        return getattr(servicio, attr)
    return servicio.precio


def backfill_precio_rango(apps, schema_editor):
    """Marca los trabajos que ya existían y usan servicios con precio personalizado.

    Los que se crearon antes de este cambio quedaron sin rango congelado y sin la
    bandera, así que el profesional podía aceptarlos sin definir el precio (y el
    sistema usaba el mínimo del rango como si fuera un precio acordado).
    """
    Trabajo = apps.get_model('trabajos', 'Trabajo')
    Servicio = apps.get_model('servicios', 'Servicio')

    pendientes = Trabajo.objects.filter(
        is_deleted=False,
        status__in=['pendiente', 'aceptado'],
        requiere_estimacion_precio=False,
    )

    actualizados = 0
    for trabajo in pendientes.iterator():
        servicios = []
        for ts in trabajo.trabajo_servicios.all():
            servicio = Servicio.objects.filter(id=ts.servicio_id).first()
            if servicio:
                servicios.append(servicio)

        con_rango = [
            s for s in servicios
            if s.precio_min is not None and s.precio_max is not None
        ]
        if not con_rango:
            continue

        trabajo.precio_min = sum(_extremo(s, 'precio_min') for s in servicios)
        trabajo.precio_max = sum(_extremo(s, 'precio_max') for s in servicios)
        # El precio que tenía era el mínimo del rango puesto por el sistema, no un
        # precio que el profesional haya definido: se limpia para que lo estime.
        trabajo.precio_final = None
        trabajo.precio_estimado = None
        trabajo.requiere_estimacion_precio = True
        trabajo.save(update_fields=[
            'precio_min', 'precio_max', 'precio_final', 'precio_estimado',
            'requiere_estimacion_precio', 'updated_at',
        ])
        actualizados += 1

    if actualizados:
        print(f'  Trabajos con precio personalizado marcados: {actualizados}')


def revertir(apps, schema_editor):
    Trabajo = apps.get_model('trabajos', 'Trabajo')
    Trabajo.objects.filter(is_deleted=False, requiere_estimacion_precio=True).update(
        requiere_estimacion_precio=False,
        precio_min=None,
        precio_max=None,
    )


class Migration(migrations.Migration):

    dependencies = [
        ('trabajos', '0014_trabajo_precio_rango_ensure'),
    ]

    operations = [
        migrations.RunPython(backfill_precio_rango, revertir),
    ]
