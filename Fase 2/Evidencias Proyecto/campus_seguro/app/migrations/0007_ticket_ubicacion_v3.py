"""
Migración 0007 – DDL v3.0
Elimina los campos de texto libre de ubicación en Ticket y hace
ubicacion_id NOT NULL (FK obligatoria a Ubicacion).

Campos eliminados:
  - edificio_texto
  - piso_texto
  - sala_texto
  - tipo_sala
  - id_sap  (SAP de la ubicación — no confundir con id_activo_sap)
  - capacidad_sala

Cambio en FK:
  - ubicacion: null=True, blank=True → NOT NULL (on_delete PROTECT)
"""
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0006_estado_catalogo_fks'),
    ]

    operations = [
        # ── 1. Eliminar campos de texto libre de ubicación ──────────
        migrations.RemoveField(model_name='ticket', name='edificio_texto'),
        migrations.RemoveField(model_name='ticket', name='piso_texto'),
        migrations.RemoveField(model_name='ticket', name='sala_texto'),
        migrations.RemoveField(model_name='ticket', name='tipo_sala'),
        migrations.RemoveField(model_name='ticket', name='id_sap'),
        migrations.RemoveField(model_name='ticket', name='capacidad_sala'),

        # ── 2. Hacer ubicacion NOT NULL (PROTECT) ───────────────────
        migrations.AlterField(
            model_name='ticket',
            name='ubicacion',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='tickets',
                to='app.ubicacion',
            ),
        ),
    ]
