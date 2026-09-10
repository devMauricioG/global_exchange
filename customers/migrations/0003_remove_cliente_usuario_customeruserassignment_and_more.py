# Generated manually for SCRUM-37

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('customers', '0002_alter_cliente_options_cliente_keycloak_id_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='CustomerUserAssignment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('is_primary_representative', models.BooleanField(default=False, help_text='Indica si el usuario es el representante legal o titular principal del cliente.', verbose_name='Representante Principal')),
                ('assigned_at', models.DateTimeField(auto_now_add=True, help_text='Marca temporal de la vinculación entre el usuario y el cliente.', verbose_name='Fecha de Asignación')),
                ('is_active', models.BooleanField(default=True, help_text='Indica si la representación se encuentra actualmente activa y autorizada.', verbose_name='Asignación Activa')),
                ('customer', models.ForeignKey(help_text='Ficha de cliente vinculada a esta asignación.', on_delete=django.db.models.deletion.CASCADE, related_name='assignments', to='customers.cliente', verbose_name='Cliente')),
                ('user', models.ForeignKey(help_text='Cuenta de usuario asociada como representante del cliente.', on_delete=django.db.models.deletion.CASCADE, related_name='customer_assignments', to=settings.AUTH_USER_MODEL, verbose_name='Usuario')),
            ],
            options={
                'verbose_name': 'Asignación de Usuario a Cliente',
                'verbose_name_plural': 'Asignaciones de Usuarios a Clientes',
                'ordering': ['-is_primary_representative', '-assigned_at'],
            },
        ),
        migrations.RemoveField(
            model_name='cliente',
            name='usuario',
        ),
        migrations.AddField(
            model_name='cliente',
            name='usuarios',
            field=models.ManyToManyField(blank=True, help_text='Usuarios autorizados para operar y representar a este cliente.', related_name='clientes_representados', through='customers.CustomerUserAssignment', to=settings.AUTH_USER_MODEL, verbose_name='Usuarios representantes'),
        ),
        migrations.AddConstraint(
            model_name='customeruserassignment',
            constraint=models.UniqueConstraint(fields=('customer', 'user'), name='unique_customer_user_assignment'),
        ),
    ]
