from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('miprimerapp', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='PersonalClinica',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('nombre', models.CharField(max_length=100)),
                ('especialidad', models.CharField(choices=[
                    ('dentista_general','Dentista General'),('asistente','Asistente'),
                    ('secretaria','Secretaria'),('implantólogo','Implantólogo'),
                    ('periodoncista','Periodoncista'),('rehabilitador','Rehabilitador'),
                    ('ortodoncista','Ortodoncista'),('odontopediatra','Odontopediatra'),
                    ('endodoncista','Endodoncista'),('patologo_oral','Patólogo Oral'),
                    ('ttm_dof','TTM y DOF'),('otro','Otro')],
                    default='dentista_general', max_length=20)),
                ('activo', models.BooleanField(default=True)),
                ('clinica', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                    related_name='personal', to='miprimerapp.clinica')),
            ],
            options={'verbose_name':'Personal de clínica','ordering':['nombre'],
                     'unique_together':{('clinica','nombre')}},
        ),
        migrations.CreateModel(
            name='StockMinimo',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('minimo', models.PositiveSmallIntegerField(default=0)),
                ('clinica', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                    related_name='stock_minimos', to='miprimerapp.clinica')),
                ('producto', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                    to='miprimerapp.producto')),
            ],
            options={'verbose_name':'Stock mínimo','unique_together':{('clinica','producto')}},
        ),
        migrations.CreateModel(
            name='VentaStock',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('cantidad', models.PositiveSmallIntegerField()),
                ('fecha', models.DateTimeField(auto_now_add=True)),
                ('clinica', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                    related_name='ventas_stock', to='miprimerapp.clinica')),
                ('producto', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                    to='miprimerapp.producto')),
                ('personal', models.ForeignKey(null=True, blank=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    to='miprimerapp.personalclinica')),
            ],
            options={'verbose_name':'Venta de stock','ordering':['-fecha']},
        ),
    ]