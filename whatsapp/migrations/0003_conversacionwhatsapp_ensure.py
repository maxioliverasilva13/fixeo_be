from django.db import migrations


def ensure_table(apps, schema_editor):
    """Crea la tabla si whatsapp.0002 quedó registrada sin ejecutar su DDL.

    Mismo caso que usuario.0010: la migración figura en django_migrations pero
    la tabla no existe ("relation whatsapp_conversacionwhatsapp does not exist").
    Usa schema_editor.create_model para que el DDL lo genere Django (identidad,
    FK a usuario, unique de wa_id), no SQL a mano.
    """
    ConversacionWhatsApp = apps.get_model('whatsapp', 'ConversacionWhatsApp')
    table = ConversacionWhatsApp._meta.db_table

    with schema_editor.connection.cursor() as cursor:
        existing = schema_editor.connection.introspection.table_names(cursor)

    if table in existing:
        return

    schema_editor.create_model(ConversacionWhatsApp)


class Migration(migrations.Migration):

    dependencies = [
        ('whatsapp', '0002_conversacionwhatsapp'),
    ]

    operations = [
        migrations.RunPython(ensure_table, migrations.RunPython.noop),
    ]
