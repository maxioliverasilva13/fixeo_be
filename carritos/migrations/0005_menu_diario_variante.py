import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('carritos', '0004_orden_motivo_cancelacion'),
        ('empresas', '0013_menu_diario'),
    ]

    operations = [
        migrations.AddField(
            model_name='ordenitem',
            name='variante_nombre',
            field=models.CharField(blank=True, default='', max_length=200),
        ),
        migrations.AddField(
            model_name='ordenitem',
            name='variante_precio_extra',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
        migrations.AddField(
            model_name='carritoitem',
            name='variante',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='carrito_items',
                to='empresas.productovariante',
            ),
        ),
        migrations.AlterUniqueTogether(
            name='carritoitem',
            unique_together=set(),
        ),
        migrations.AddConstraint(
            model_name='carritoitem',
            constraint=models.UniqueConstraint(
                fields=('carrito', 'producto', 'variante'),
                name='unique_carrito_producto_variante',
                nulls_distinct=False,
            ),
        ),
    ]
