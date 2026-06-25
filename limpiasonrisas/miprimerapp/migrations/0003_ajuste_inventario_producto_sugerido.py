from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('miprimerapp', '0002_mi_stock'),
    ]

    operations = [
        migrations.CreateModel(
            name='AjusteInventario',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('cantidad', models.IntegerField(default=0)),
                ('nota', models.CharField(blank=True, max_length=200)),
                ('fecha', models.DateTimeField(auto_now=True)),
                ('clinica', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                    related_name='ajustes_inventario', to='miprimerapp.clinica')),
                ('producto', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                    to='miprimerapp.producto')),
            ],
            options={
                'verbose_name': 'Ajuste de inventario',
                'verbose_name_plural': 'Ajustes de inventario',
                'ordering': ['producto__nombre'],
                'unique_together': {('clinica', 'producto')},
            },
        ),
        migrations.CreateModel(
            name='ProductoSugerido',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('nombre_producto', models.CharField(max_length=150)),
                ('marca', models.CharField(blank=True, max_length=80)),
                ('uso', models.TextField(blank=True)),
                ('cantidad_mensual', models.PositiveSmallIntegerField(blank=True, null=True)),
                ('revisado', models.BooleanField(default=False)),
                ('fecha', models.DateTimeField(auto_now_add=True)),
                ('clinica', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                    related_name='productos_sugeridos', to='miprimerapp.clinica')),
            ],
            options={
                'verbose_name': 'Producto sugerido',
                'verbose_name_plural': 'Productos sugeridos',
                'ordering': ['-fecha'],
            },
        ),
    ]