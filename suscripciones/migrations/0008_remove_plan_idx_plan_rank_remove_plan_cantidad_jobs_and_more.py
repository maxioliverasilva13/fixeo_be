from django.db import migrations

# NO-OP a propósito: este nombre de migración ya había quedado registrado como
# aplicado en algunas bases de desarrollo (incluía RemoveField de
# cantidad_jobs/jobs_restantes, nunca commiteado). Reescribirlo vacío evita dos
# problemas: 1) en esas bases, Django ya lo marca aplicado y no lo vuelve a
# correr, así que estas operaciones vacías no hacen nada ahí; 2) en cualquier
# base nueva (prod, un clon limpio) corre por primera vez sin remover nada. La
# migración 0011 (al final de la cadena) deja cantidad_jobs/jobs_restantes y el
# índice compuesto en el estado correcto para TODAS las bases, sin importar por
# cuál de los dos caminos llegaron acá.
class Migration(migrations.Migration):

    dependencies = [
        ('suscripciones', '0007_remove_campanamarketing_precio_tachado_and_more'),
    ]

    operations = []
