from django.db import migrations

# Repara, en cualquier base, el estado final que ya espera el resto del
# historial de migraciones y el modelo actual: cantidad_jobs/jobs_restantes
# presentes y el índice compuesto correcto. Todo con SQL idempotente, así que
# es un no-op seguro en las bases que ya estaban bien (prod, clones nuevos) y
# repara las que quedaron con las columnas borradas por la migración 0008
# (ver el comentario en ese archivo).
ADD_CANTIDAD_JOBS = """
ALTER TABLE plan ADD COLUMN IF NOT EXISTS cantidad_jobs integer NOT NULL DEFAULT 5;
"""

ADD_JOBS_RESTANTES = """
ALTER TABLE subscripcion ADD COLUMN IF NOT EXISTS jobs_restantes integer NOT NULL DEFAULT 0;
"""

FIX_INDEX = """
DROP INDEX IF EXISTS idx_plan_rank;
CREATE INDEX idx_plan_rank ON plan (precio, cantidad_jobs);
"""


class Migration(migrations.Migration):

    dependencies = [
        ('suscripciones', '0010_plan_color_plan_slogan'),
    ]

    operations = [
        migrations.RunSQL(sql=ADD_CANTIDAD_JOBS, reverse_sql=migrations.RunSQL.noop),
        migrations.RunSQL(sql=ADD_JOBS_RESTANTES, reverse_sql=migrations.RunSQL.noop),
        migrations.RunSQL(sql=FIX_INDEX, reverse_sql=migrations.RunSQL.noop),
    ]
