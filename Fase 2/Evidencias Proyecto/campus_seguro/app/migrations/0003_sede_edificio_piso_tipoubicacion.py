"""
Migración de parche: crea las tablas Sede, Edificio, Piso y TipoUbicacion
que el compañero agregó al modelo pero olvidó generar como migración nueva
(modificó 0001_initial que ya estaba aplicada).

También migra los 217 registros de app_ubicacion del esquema plano
(sede/edificio/piso como CharField) al nuevo esquema relacional,
y reemplaza la columna 'sede' VARCHAR de app_usuario por 'sede_id' FK.
"""
from django.db import migrations


TIPOS_DISPLAY = {
    'aula': 'Aula',
    'baño': 'Baño',
    'laboratorio': 'Laboratorio',
    'pasillo': 'Pasillo',
    'escalera': 'Escalera',
    'ascensor': 'Ascensor',
    'casino': 'Casino',
    'oficina': 'Oficina',
    'bodega': 'Bodega',
    'sala_reuniones': 'Sala de reuniones',
}


def crear_estructura_relacional(apps, schema_editor):
    c = schema_editor.connection.cursor()

    # Leer combinaciones únicas de la tabla plana actual
    c.execute(
        "SELECT DISTINCT sede, edificio, piso, tipo FROM app_ubicacion ORDER BY sede, edificio, piso"
    )
    filas = c.fetchall()

    # — Sedes —
    sedes = {}
    for nombre in sorted({f[0] for f in filas}):
        c.execute("INSERT INTO app_sede (nombre) VALUES (%s)", [nombre])
        sedes[nombre] = c.lastrowid

    # — Edificios —
    edificios = {}
    for sede_nombre, ed_nombre in sorted({(f[0], f[1]) for f in filas}):
        c.execute(
            "INSERT INTO app_edificio (sede_id, nombre) VALUES (%s, %s)",
            [sedes[sede_nombre], ed_nombre],
        )
        edificios[(sede_nombre, ed_nombre)] = c.lastrowid

    # — Pisos —
    pisos = {}
    for sede_nombre, ed_nombre, piso_num in sorted(
        {(f[0], f[1], f[2]) for f in filas}
    ):
        c.execute(
            "INSERT INTO app_piso (edificio_id, numero) VALUES (%s, %s)",
            [edificios[(sede_nombre, ed_nombre)], piso_num],
        )
        pisos[(sede_nombre, ed_nombre, piso_num)] = c.lastrowid

    # — TipoUbicacion —
    tipos = {}
    for codigo in sorted({f[3] for f in filas}):
        display = TIPOS_DISPLAY.get(codigo, codigo.replace('_', ' ').capitalize())
        c.execute(
            "INSERT INTO app_tipoubicacion (codigo, nombre_display) VALUES (%s, %s)",
            [codigo, display],
        )
        tipos[codigo] = c.lastrowid

    # Leer todas las ubicaciones existentes antes de eliminar la tabla
    c.execute(
        "SELECT id, sede, edificio, piso, sala, tipo, id_sap, capacidad FROM app_ubicacion"
    )
    ubicaciones = c.fetchall()

    # Recrear app_ubicacion con el nuevo esquema relacional
    c.execute(
        """
        CREATE TABLE "new__app_ubicacion" (
            "id"         integer NOT NULL PRIMARY KEY AUTOINCREMENT,
            "piso_id"    bigint  NOT NULL REFERENCES "app_piso" ("id") DEFERRABLE INITIALLY DEFERRED,
            "tipo_id"    bigint  NOT NULL REFERENCES "app_tipoubicacion" ("id") DEFERRABLE INITIALLY DEFERRED,
            "sala"       varchar(50)  NOT NULL,
            "id_sap"     varchar(50)  NULL UNIQUE,
            "capacidad"  integer unsigned NULL CHECK ("capacidad" >= 0)
        )
        """
    )

    for ub_id, sede, edificio, piso, sala, tipo, id_sap, capacidad in ubicaciones:
        piso_id = pisos.get((sede, edificio, piso))
        tipo_id = tipos.get(tipo)
        if piso_id and tipo_id:
            c.execute(
                "INSERT INTO new__app_ubicacion (id, piso_id, tipo_id, sala, id_sap, capacidad) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                [ub_id, piso_id, tipo_id, sala, id_sap, capacidad],
            )

    c.execute("DROP TABLE app_ubicacion")
    c.execute("ALTER TABLE new__app_ubicacion RENAME TO app_ubicacion")
    c.execute("CREATE INDEX app_ubicacion_piso_id_idx ON app_ubicacion (piso_id)")
    c.execute("CREATE INDEX app_ubicacion_tipo_id_idx ON app_ubicacion (tipo_id)")
    c.execute(
        "CREATE UNIQUE INDEX app_ubicacion_piso_id_sala_uniq ON app_ubicacion (piso_id, sala)"
    )


def migrar_usuario_sede(apps, schema_editor):
    c = schema_editor.connection.cursor()

    # Agregar columna sede_id (FK nullable — los usuarios actuales no tenían sede asignada)
    c.execute(
        'ALTER TABLE "app_usuario" ADD COLUMN "sede_id" bigint NULL '
        'REFERENCES "app_sede" ("id") DEFERRABLE INITIALLY DEFERRED'
    )
    c.execute(
        'CREATE INDEX "app_usuario_sede_id_4e26e23b" ON "app_usuario" ("sede_id")'
    )

    # Eliminar la antigua columna sede VARCHAR (SQLite >= 3.35 soporta DROP COLUMN)
    c.execute('ALTER TABLE "app_usuario" DROP COLUMN "sede"')


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0002_alter_transicionestado_rol_requerido_and_more'),
    ]

    operations = [
        # 1. Crear tablas nuevas
        migrations.RunSQL(
            sql='''
                CREATE TABLE "app_sede" (
                    "id"        integer NOT NULL PRIMARY KEY AUTOINCREMENT,
                    "nombre"    varchar(100) NOT NULL UNIQUE,
                    "direccion" varchar(250) NULL
                )
            ''',
            reverse_sql='DROP TABLE IF EXISTS "app_sede"',
        ),
        migrations.RunSQL(
            sql='''
                CREATE TABLE "app_edificio" (
                    "id"      integer NOT NULL PRIMARY KEY AUTOINCREMENT,
                    "sede_id" bigint  NOT NULL REFERENCES "app_sede" ("id") DEFERRABLE INITIALLY DEFERRED,
                    "nombre"  varchar(100) NOT NULL,
                    UNIQUE ("sede_id", "nombre")
                )
            ''',
            reverse_sql='DROP TABLE IF EXISTS "app_edificio"',
        ),
        migrations.RunSQL(
            sql='''
                CREATE TABLE "app_piso" (
                    "id"          integer NOT NULL PRIMARY KEY AUTOINCREMENT,
                    "edificio_id" bigint  NOT NULL REFERENCES "app_edificio" ("id") DEFERRABLE INITIALLY DEFERRED,
                    "numero"      varchar(10) NOT NULL,
                    UNIQUE ("edificio_id", "numero")
                )
            ''',
            reverse_sql='DROP TABLE IF EXISTS "app_piso"',
        ),
        migrations.RunSQL(
            sql='''
                CREATE TABLE "app_tipoubicacion" (
                    "id"             integer NOT NULL PRIMARY KEY AUTOINCREMENT,
                    "codigo"         varchar(30)  NOT NULL UNIQUE,
                    "nombre_display" varchar(100) NOT NULL
                )
            ''',
            reverse_sql='DROP TABLE IF EXISTS "app_tipoubicacion"',
        ),
        # 2. Migrar datos de ubicaciones y reconstruir la tabla con nuevo esquema
        migrations.RunPython(crear_estructura_relacional, migrations.RunPython.noop),
        # 3. Arreglar app_usuario: reemplazar 'sede' VARCHAR por 'sede_id' FK
        migrations.RunPython(migrar_usuario_sede, migrations.RunPython.noop),
    ]
