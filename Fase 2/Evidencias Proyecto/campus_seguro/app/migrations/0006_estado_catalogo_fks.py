# Generated manually – DDL v2.0 alignment
# Crea EstadoCatalogo + TransicionEstado y convierte los 6 campos
# VARCHAR de estado a ForeignKey real, preservando datos existentes.
from django.db import migrations, models
import django.db.models.deletion


# ─────────────────────────────────────────────────────────────────
# Datos iniciales del catálogo (30 estados = DDL v2.0 INSERT block)
# ─────────────────────────────────────────────────────────────────
ESTADOS_INICIALES = [
    # ticket
    dict(entidad='ticket', codigo='enviado',       nombre_display='Enviado',       es_inicial=True,  es_final=False, orden=1,  color_hex='#6c757d'),
    dict(entidad='ticket', codigo='en_proceso',    nombre_display='En Proceso',    es_inicial=False, es_final=False, orden=2,  color_hex='#007bff'),
    dict(entidad='ticket', codigo='en_validacion', nombre_display='En Validación', es_inicial=False, es_final=False, orden=3,  color_hex='#fd7e14'),
    dict(entidad='ticket', codigo='validado',      nombre_display='Validado',      es_inicial=False, es_final=False, orden=4,  color_hex='#20c997'),
    dict(entidad='ticket', codigo='en_mantencion', nombre_display='En Mantención', es_inicial=False, es_final=False, orden=5,  color_hex='#17a2b8'),
    dict(entidad='ticket', codigo='reparado',      nombre_display='Reparado',      es_inicial=False, es_final=False, orden=6,  color_hex='#28a745'),
    dict(entidad='ticket', codigo='pausado',       nombre_display='Pausado',       es_inicial=False, es_final=False, orden=7,  color_hex='#ffc107'),
    dict(entidad='ticket', codigo='no_reparado',   nombre_display='No Reparado',   es_inicial=False, es_final=True,  orden=8,  color_hex='#dc3545'),
    dict(entidad='ticket', codigo='cerrado',       nombre_display='Cerrado',       es_inicial=False, es_final=True,  orden=9,  color_hex='#343a40'),
    dict(entidad='ticket', codigo='cancelado',     nombre_display='Cancelado',     es_inicial=False, es_final=True,  orden=10, color_hex='#6f42c1'),
    dict(entidad='ticket', codigo='revocado',      nombre_display='Revocado',      es_inicial=False, es_final=True,  orden=11, color_hex='#e83e8c'),
    dict(entidad='ticket', codigo='eliminado',     nombre_display='Eliminado',     es_inicial=False, es_final=True,  orden=12, color_hex='#6c757d'),
    # ticket_sub
    dict(entidad='ticket_sub', codigo='pendiente_revision',  nombre_display='Pendiente Revisión',    es_inicial=True,  es_final=False, orden=1),
    dict(entidad='ticket_sub', codigo='revisado',            nombre_display='Revisado',              es_inicial=False, es_final=False, orden=2),
    dict(entidad='ticket_sub', codigo='asignado_mantencion', nombre_display='Asignado a Mantención', es_inicial=False, es_final=False, orden=3),
    dict(entidad='ticket_sub', codigo='escalado',            nombre_display='Escalado',              es_inicial=False, es_final=True,  orden=4),
    dict(entidad='ticket_sub', codigo='asignado_guardia',    nombre_display='Asignado a Guardia',    es_inicial=False, es_final=False, orden=5),
    dict(entidad='ticket_sub', codigo='asignado_tecnico',    nombre_display='Asignado a Técnico',    es_inicial=False, es_final=False, orden=6),
    # cuenta
    dict(entidad='cuenta', codigo='pendiente',  nombre_display='Pendiente',  es_inicial=True,  es_final=False, orden=1, color_hex='#ffc107'),
    dict(entidad='cuenta', codigo='activa',     nombre_display='Activa',     es_inicial=False, es_final=False, orden=2, color_hex='#28a745'),
    dict(entidad='cuenta', codigo='suspendida', nombre_display='Suspendida', es_inicial=False, es_final=False, orden=3, color_hex='#fd7e14'),
    dict(entidad='cuenta', codigo='rechazada',  nombre_display='Rechazada',  es_inicial=False, es_final=True,  orden=4, color_hex='#dc3545'),
    # asignacion
    dict(entidad='asignacion', codigo='activa',     nombre_display='Activa',     es_inicial=True,  es_final=False, orden=1),
    dict(entidad='asignacion', codigo='completada', nombre_display='Completada', es_inicial=False, es_final=True,  orden=2),
    dict(entidad='asignacion', codigo='cancelada',  nombre_display='Cancelada',  es_inicial=False, es_final=True,  orden=3),
    dict(entidad='asignacion', codigo='pendiente',  nombre_display='Pendiente',  es_inicial=False, es_final=False, orden=4),
    # inasistencia
    dict(entidad='inasistencia', codigo='pendiente', nombre_display='Pendiente', es_inicial=True,  es_final=False, orden=1),
    dict(entidad='inasistencia', codigo='aprobada',  nombre_display='Aprobada',  es_inicial=False, es_final=True,  orden=2),
    dict(entidad='inasistencia', codigo='rechazada', nombre_display='Rechazada', es_inicial=False, es_final=True,  orden=3),
    # material_faltante
    dict(entidad='material_faltante', codigo='pendiente',  nombre_display='Pendiente',  es_inicial=True,  es_final=False, orden=1),
    dict(entidad='material_faltante', codigo='solicitado', nombre_display='Solicitado', es_inicial=False, es_final=False, orden=2),
    dict(entidad='material_faltante', codigo='recibido',   nombre_display='Recibido',   es_inicial=False, es_final=True,  orden=3),
    dict(entidad='material_faltante', codigo='cancelado',  nombre_display='Cancelado',  es_inicial=False, es_final=True,  orden=4),
]


def poblar_estado_catalogo(apps, schema_editor):
    EstadoCatalogo = apps.get_model('app', 'EstadoCatalogo')
    for data in ESTADOS_INICIALES:
        EstadoCatalogo.objects.get_or_create(
            entidad=data['entidad'],
            codigo=data['codigo'],
            defaults=data,
        )


# ─────────────────────────────────────────────────────────────────
# Funciones de migración de datos (VARCHAR → FK)
# ─────────────────────────────────────────────────────────────────
def _build_map(apps, entidad):
    EC = apps.get_model('app', 'EstadoCatalogo')
    return {ec.codigo: ec for ec in EC.objects.filter(entidad=entidad)}


def migrar_ticket_estado(apps, schema_editor):
    Ticket = apps.get_model('app', 'Ticket')
    ec_map = _build_map(apps, 'ticket')
    default = ec_map.get('enviado')
    for t in Ticket.objects.all():
        t.estado = ec_map.get(t.estado_legado or '', default) or default
        t.save(update_fields=['estado'])


def migrar_ticket_sub_estado(apps, schema_editor):
    Ticket = apps.get_model('app', 'Ticket')
    ec_map = _build_map(apps, 'ticket_sub')
    for t in Ticket.objects.filter(sub_estado_legado__isnull=False):
        ec = ec_map.get(t.sub_estado_legado)
        if ec:
            t.sub_estado = ec
            t.save(update_fields=['sub_estado'])


def migrar_usuario_estado_cuenta(apps, schema_editor):
    Usuario = apps.get_model('app', 'Usuario')
    ec_map = _build_map(apps, 'cuenta')
    default = ec_map.get('pendiente')
    for u in Usuario.objects.all():
        u.estado_cuenta = ec_map.get(u.estado_cuenta_legado or '', default) or default
        u.save(update_fields=['estado_cuenta'])


def migrar_asignacion_estado(apps, schema_editor):
    AsignacionTicket = apps.get_model('app', 'AsignacionTicket')
    ec_map = _build_map(apps, 'asignacion')
    default = ec_map.get('activa')
    for a in AsignacionTicket.objects.all():
        a.estado = ec_map.get(a.estado_legado or '', default) or default
        a.save(update_fields=['estado'])


def migrar_inasistencia_estado(apps, schema_editor):
    Inasistencia = apps.get_model('app', 'Inasistencia')
    ec_map = _build_map(apps, 'inasistencia')
    default = ec_map.get('pendiente')
    for i in Inasistencia.objects.all():
        i.estado = ec_map.get(i.estado_legado or '', default) or default
        i.save(update_fields=['estado'])


def migrar_mat_faltante_estado(apps, schema_editor):
    MaterialesFaltantes = apps.get_model('app', 'MaterialesFaltantes')
    ec_map = _build_map(apps, 'material_faltante')
    default = ec_map.get('pendiente')
    for m in MaterialesFaltantes.objects.all():
        m.estado = ec_map.get(m.estado_legado or '', default) or default
        m.save(update_fields=['estado'])


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0005_enc_seguridad_subestado_asignacion_historial'),
    ]

    operations = [
        # ── 1. Crear EstadoCatalogo ──────────────────────────────
        migrations.CreateModel(
            name='EstadoCatalogo',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('entidad', models.CharField(choices=[('ticket', 'Ticket'), ('ticket_sub', 'Sub-estado de Ticket'), ('cuenta', 'Cuenta de Usuario'), ('asignacion', 'Asignación de Ticket'), ('inasistencia', 'Inasistencia'), ('material_faltante', 'Material Faltante')], max_length=20)),
                ('codigo', models.CharField(max_length=30)),
                ('nombre_display', models.CharField(max_length=100)),
                ('descripcion', models.CharField(blank=True, max_length=300, null=True)),
                ('es_inicial', models.BooleanField(default=False)),
                ('es_final', models.BooleanField(default=False)),
                ('orden', models.PositiveIntegerField(default=0)),
                ('color_hex', models.CharField(blank=True, max_length=7, null=True)),
                ('activo', models.BooleanField(default=True)),
            ],
            options={
                'verbose_name': 'Estado del Catálogo',
                'verbose_name_plural': 'Catálogo de Estados',
                'ordering': ['entidad', 'orden'],
            },
        ),
        migrations.AddConstraint(
            model_name='estadocatalogo',
            constraint=models.UniqueConstraint(fields=['entidad', 'codigo'], name='uq_estado_entidad_codigo'),
        ),

        # ── 2. Crear TransicionEstado ────────────────────────────
        migrations.CreateModel(
            name='TransicionEstado',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('rol_requerido', models.CharField(blank=True, choices=[('usuario', 'Usuario Base'), ('gestor', 'Gestor'), ('enc_seguridad', 'Encargado de Seguridad'), ('guardia', 'Guardia'), ('mantencion', 'Mantención')], max_length=20, null=True)),
                ('descripcion', models.CharField(blank=True, max_length=200, null=True)),
                ('activo', models.BooleanField(default=True)),
                ('estado_destino', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='transiciones_destino', to='app.estadocatalogo')),
                ('estado_origen', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='transiciones_origen', to='app.estadocatalogo')),
            ],
            options={
                'verbose_name': 'Transición de Estado',
                'verbose_name_plural': 'Transiciones de Estado',
            },
        ),
        migrations.AddConstraint(
            model_name='transicionestado',
            constraint=models.UniqueConstraint(fields=['estado_origen', 'estado_destino'], name='uq_transicion_estados'),
        ),

        # ── 3. Poblar los 30 estados iniciales ──────────────────
        migrations.RunPython(poblar_estado_catalogo, migrations.RunPython.noop),

        # ── 4. Ticket.estado (VARCHAR → FK) ──────────────────────
        migrations.RenameField('Ticket', 'estado', 'estado_legado'),
        migrations.AddField(
            model_name='ticket',
            name='estado',
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='tickets_estado',
                to='app.estadocatalogo',
                limit_choices_to={'entidad': 'ticket'},
            ),
        ),
        migrations.RunPython(migrar_ticket_estado, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='ticket',
            name='estado',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='tickets_estado',
                to='app.estadocatalogo',
                limit_choices_to={'entidad': 'ticket'},
            ),
        ),
        migrations.RemoveField('Ticket', 'estado_legado'),

        # ── 5. Ticket.sub_estado (VARCHAR → FK, nullable) ────────
        migrations.RenameField('Ticket', 'sub_estado', 'sub_estado_legado'),
        migrations.AddField(
            model_name='ticket',
            name='sub_estado',
            field=models.ForeignKey(
                null=True, blank=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='tickets_sub_estado',
                to='app.estadocatalogo',
                limit_choices_to={'entidad': 'ticket_sub'},
            ),
        ),
        migrations.RunPython(migrar_ticket_sub_estado, migrations.RunPython.noop),
        migrations.RemoveField('Ticket', 'sub_estado_legado'),

        # ── 6. Usuario.estado_cuenta (VARCHAR → FK) ───────────────
        migrations.RenameField('Usuario', 'estado_cuenta', 'estado_cuenta_legado'),
        migrations.AddField(
            model_name='usuario',
            name='estado_cuenta',
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='usuarios',
                to='app.estadocatalogo',
                limit_choices_to={'entidad': 'cuenta'},
            ),
        ),
        migrations.RunPython(migrar_usuario_estado_cuenta, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='usuario',
            name='estado_cuenta',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='usuarios',
                to='app.estadocatalogo',
                limit_choices_to={'entidad': 'cuenta'},
            ),
        ),
        migrations.RemoveField('Usuario', 'estado_cuenta_legado'),

        # ── 7. AsignacionTicket.estado (VARCHAR → FK) ─────────────
        migrations.RenameField('AsignacionTicket', 'estado', 'estado_legado'),
        migrations.AddField(
            model_name='asignacionticket',
            name='estado',
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='asignaciones_estado',
                to='app.estadocatalogo',
                limit_choices_to={'entidad': 'asignacion'},
            ),
        ),
        migrations.RunPython(migrar_asignacion_estado, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='asignacionticket',
            name='estado',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='asignaciones_estado',
                to='app.estadocatalogo',
                limit_choices_to={'entidad': 'asignacion'},
            ),
        ),
        migrations.RemoveField('AsignacionTicket', 'estado_legado'),

        # ── 8. Inasistencia.estado (VARCHAR → FK) ─────────────────
        migrations.RenameField('Inasistencia', 'estado', 'estado_legado'),
        migrations.AddField(
            model_name='inasistencia',
            name='estado',
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='inasistencias_estado',
                to='app.estadocatalogo',
                limit_choices_to={'entidad': 'inasistencia'},
            ),
        ),
        migrations.RunPython(migrar_inasistencia_estado, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='inasistencia',
            name='estado',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='inasistencias_estado',
                to='app.estadocatalogo',
                limit_choices_to={'entidad': 'inasistencia'},
            ),
        ),
        migrations.RemoveField('Inasistencia', 'estado_legado'),

        # ── 9. MaterialesFaltantes.estado (VARCHAR → FK) ──────────
        migrations.RenameField('MaterialesFaltantes', 'estado', 'estado_legado'),
        migrations.AddField(
            model_name='materialesfaltantes',
            name='estado',
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='materiales_faltantes_estado',
                to='app.estadocatalogo',
                limit_choices_to={'entidad': 'material_faltante'},
            ),
        ),
        migrations.RunPython(migrar_mat_faltante_estado, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='materialesfaltantes',
            name='estado',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='materiales_faltantes_estado',
                to='app.estadocatalogo',
                limit_choices_to={'entidad': 'material_faltante'},
            ),
        ),
        migrations.RemoveField('MaterialesFaltantes', 'estado_legado'),

        # ── 10. HistorialAcciones.duracion_estado_anterior_min ────
        migrations.AddField(
            model_name='historialacciones',
            name='duracion_estado_anterior_min',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
    ]
