from django.db import migrations, models
import django.db.models.deletion

CARRERAS_SEED = [
    # (nombre, escuela)
    ('Ingeniería en Informática',                                        'Escuela de Informática y Telecomunicaciones'),
    ('Ingeniería en Redes y Telecomunicaciones',                         'Escuela de Informática y Telecomunicaciones'),
    ('Administración en Turismo y Hospitalidad Mención Gestión de Destinos Turísticos', 'Escuela de Turismo y Hospitalidad'),
    ('Administración en Turismo y Hospitalidad Mención Gestión para el Ecoturismo',      'Escuela de Turismo y Hospitalidad'),
    ('Ingeniería en Marketing Digital',                                  'Escuela de Administración y Negocios'),
    ('Ingeniería en Gestión Logística',                                  'Escuela de Administración y Negocios'),
    ('Ingeniería en Comercio Exterior',                                  'Escuela de Administración y Negocios'),
    ('Ingeniería en Administración Mención Gestión de Personas',         'Escuela de Administración y Negocios'),
    ('Ingeniería en Administración Mención Finanzas',                    'Escuela de Administración y Negocios'),
    ('Técnico en Electricidad y Automatización Industrial',              'Escuela de Ingeniería y Recursos Naturales'),
    ('Ingeniería en Maquinaria y Vehículos Pesados',                     'Escuela de Ingeniería y Recursos Naturales'),
    ('Ingeniería en Mantenimiento Industrial',                           'Escuela de Ingeniería y Recursos Naturales'),
    ('Ingeniería en Electricidad y Automatización Industrial',           'Escuela de Ingeniería y Recursos Naturales'),
    ('Ingeniería en Mecánica Automotriz y Autotrónica',                  'Escuela de Ingeniería y Recursos Naturales'),
    ('Informática Biomédica',                                            'Escuela de Salud y Bienestar'),
    ('Técnico en Enfermería',                                            'Escuela de Salud y Bienestar'),
    ('Técnico en Odontología',                                           'Escuela de Salud y Bienestar'),
    ('Ilustración para Contextos Globales',                              'Escuela de Diseño'),
    ('Diseño Industrial e Innovación en Productos',                      'Escuela de Diseño'),
    ('Diseño Gráfico',                                                   'Escuela de Diseño'),
    ('Gastronomía Internacional',                                        'Escuela de Gastronomía'),
    ('Comunicación Audiovisual',                                         'Escuela de Comunicación'),
    ('Relaciones Públicas y Comunicación Organizacional',               'Escuela de Comunicación'),
    ('Publicidad',                                                       'Escuela de Comunicación'),
    ('Animación Digital',                                                'Escuela de Comunicación'),
    ('Ingeniería en Sonido',                                             'Escuela de Comunicación'),
    ('Ingeniería en Construcción',                                       'Escuela de Construcción'),
    ('Ingeniería en Prevención de Riesgos',                             'Escuela de Construcción'),
]


def seed_carreras(apps, schema_editor):
    Carrera = apps.get_model('app', 'Carrera')
    Sede = apps.get_model('app', 'Sede')
    sede = Sede.objects.filter(nombre__icontains='San Andr').first()
    for nombre, escuela in CARRERAS_SEED:
        Carrera.objects.get_or_create(
            nombre=nombre,
            defaults={'escuela': escuela, 'sede': sede, 'activa': True},
        )


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0003_unique_asignacion_ticket'),
    ]

    operations = [
        # 1. Crear tabla Carrera
        migrations.CreateModel(
            name='Carrera',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nombre', models.CharField(max_length=150, unique=True)),
                ('escuela', models.CharField(blank=True, max_length=150)),
                ('activa', models.BooleanField(default=True, help_text='Desmarcar para ocultarla del formulario de registro.')),
                ('sede', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='carreras',
                    to='app.sede',
                    help_text='Sede donde se imparte. Null = disponible en todas.',
                )),
            ],
            options={
                'verbose_name': 'Carrera',
                'verbose_name_plural': 'Carreras',
                'ordering': ['escuela', 'nombre'],
            },
        ),
        # 2. Poblar con las carreras de Duoc San Andrés
        migrations.RunPython(seed_carreras, migrations.RunPython.noop),
        # 3. Eliminar el antiguo CharField carrera de Usuario
        migrations.RemoveField(model_name='usuario', name='carrera'),
        # 4. Agregar FK carrera → Carrera en Usuario
        migrations.AddField(
            model_name='usuario',
            name='carrera',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='alumnos',
                to='app.carrera',
            ),
        ),
    ]
