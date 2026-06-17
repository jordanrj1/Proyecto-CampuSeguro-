# Base de Datos Local, Auth0 y Sincronización entre Entornos

**Sesión:** Junio 2026  
**Responsable:** Jordan Garcia  
**Estado:** Problema resuelto – Recomendaciones a futuro documentadas

---

## El problema que apareció

Al intentar iniciar sesión con `gestor@duocuc.cl`, el sistema respondió con el mensaje "Tu cuenta no está registrada en Campus Seguro. Solicita registro institucional." La contraseña era correcta en Auth0, el usuario existe en Auth0, y las credenciales se habían cambiado y restaurado sin efecto. El cambio de contraseña en Auth0 no tenía relación con el problema.

---

## Por qué pasó

Campus Seguro usa dos sistemas completamente separados para guardar información de usuarios.

**Auth0** guarda las credenciales: el correo, la contraseña, y los metadatos de rol (`campus_rol`) y estado de cuenta (`campus_estado`) en el campo `app_metadata`. Auth0 vive en la nube y es compartido por todos los entornos sin importar desde qué máquina se ejecute el sistema.

**La base de datos SQLite local** (`db.sqlite3`) guarda todo lo demás: nombre, RUT, rol Django, estado de cuenta como objeto relacionado, tickets, inasistencias, materiales, y cualquier dato de la aplicación. Este archivo vive en la máquina donde se ejecuta `python manage.py runserver` y **no se comparte con otros entornos ni se sube al repositorio** (está en `.gitignore`).

El flujo de login funciona así: cuando alguien envía sus credenciales, el sistema primero las manda a Auth0 para verificar. Si Auth0 confirma que la contraseña es correcta, Django busca el correo en su BD local para obtener el objeto Usuario con rol, estado y todos sus datos. Si ese correo no existe en la BD local, el sistema muestra el mensaje de error aunque Auth0 haya autenticado correctamente.

La BD local estaba completamente vacía (0 usuarios). Esto ocurre cuando se trabaja en una máquina nueva, se borra el `db.sqlite3`, o se reinician las migraciones desde cero.

---

## Diagnóstico que confirmó el problema

```bash
python manage.py shell -c "
from app.models import Usuario
print('Usuarios en BD:', Usuario.objects.count())
"
```

Respuesta esperada cuando el problema existe:

```
Usuarios en BD: 0
```

Respuesta esperada cuando la BD está en orden:

```
Usuarios en BD: 13
```

---

## Solución inmediata aplicada

Se ejecutaron dos comandos en secuencia.

Primero se creó el gestor con `crear_gestor` porque este rol necesita existir antes que cualquier otra cuenta, y su RUT es requerido como campo único en la BD local. El RUT puede ser un placeholder temporal porque Auth0 no lo almacena y solo sirve como identificador local:

```bash
python manage.py crear_gestor \
  --email gestor@duocuc.cl \
  --rut 12.345.678-9 \
  --nombre Jordan \
  --apellido Garcia
```

Respuesta esperada:

```
  OK Gestor creado correctamente

    Nombre:   Jordan Garcia
    Correo:   gestor@duocuc.cl
    RUT:      12.345.678-9
    Rol:      gestor
    Estado:   activa
    Auth0 ID: se vincula automáticamente en el primer login
```

Luego se ejecutó `sincronizar_auth0` que consulta la Management API de Auth0, trae todos los usuarios registrados en la nube y los crea en la BD local. Este comando nunca sobreescribe usuarios que ya existen, solo crea los que faltan:

```bash
python manage.py sincronizar_auth0
```

Respuesta esperada:

```
  >> 13 usuario(s) encontrado(s) en Auth0

  OK tecnico_mantenedor@duocuc.cl        rol=mantencion   estado=activa
  OK mo.munoz@duocuc.cl                  rol=usuario      estado=activa
  OK mantenedor_duoc@duocuc.cl           rol=mantencion   estado=activa
  OK guardia@duocuc.cl                   rol=guardia      estado=activa
  ...

  Creados : 12
  Omitidos (ya existían): 1
```

El "omitido" es el gestor que ya se había creado en el paso anterior. Eso es correcto.

---

## Procedimiento completo para levantar un entorno nuevo desde cero

Cada vez que se trabaje en una máquina nueva o se reinicie la BD, el orden correcto es:

```bash
python manage.py migrate
```

Este comando aplica todas las migraciones y crea las tablas. Sin esto los siguientes comandos fallan.

```bash
python manage.py poblar_sistema
```

Este comando carga los catálogos base: estados de tickets, estados de cuenta, categorías, materiales iniciales. Sin estos datos el sistema no puede crear tickets ni usuarios.

```bash
python manage.py crear_gestor \
  --email gestor@duocuc.cl \
  --rut TU_RUT_REAL \
  --nombre Jordan \
  --apellido Garcia
```

Este comando crea el usuario gestor con cuenta activa. Es el único que requiere RUT real (o placeholder). El campo RUT puede corregirse después desde el panel de administración.

```bash
python manage.py sincronizar_auth0
```

Este comando importa todos los usuarios registrados en Auth0 a la BD local. Asigna RUT temporal con el formato `SYNC-XXXXXXX` que el gestor puede corregir al aprobar cada cuenta. Los roles y estados de cuenta se importan desde el `app_metadata` que Auth0 almacenó cuando el usuario se registró.

Con estos cuatro comandos el entorno queda completamente operativo con todos los usuarios, roles y datos de catálogo correctos.

---

## Verificación posterior

Para confirmar que todos los usuarios quedaron bien importados:

```bash
python manage.py shell -c "
from app.models import Usuario
for u in Usuario.objects.all():
    print(f'{u.correo_institucional:<40} rol={u.rol:<12} estado={u.estado_cuenta.codigo}')
"
```

Respuesta esperada:

```
gestor@duocuc.cl                         rol=gestor       estado=activa
tecnico_mantenedor@duocuc.cl             rol=mantencion   estado=activa
mo.munoz@duocuc.cl                       rol=usuario      estado=activa
guardia@duocuc.cl                        rol=guardia      estado=activa
...
```

Si algún usuario aparece con `rol=usuario` siendo que debería tener otro rol, es porque su `app_metadata.campus_rol` en Auth0 no estaba configurado correctamente cuando se registró. Se puede corregir desde el panel del gestor en la sección de usuarios, o desde el panel de Auth0 editando el `app_metadata` del usuario.

---

## Por qué `sincronizar_auth0` requiere las credenciales de Management API

Auth0 tiene dos APIs distintas. La API pública de autenticación solo permite verificar credenciales. La Management API permite leer la lista de todos los usuarios, ver sus metadatos y modificarlos. Para usar la Management API se necesita un Client ID y un Client Secret específicos que se configuran en el `.env` del proyecto:

```
AUTH0_MGMT_CLIENT_ID=...
AUTH0_MGMT_CLIENT_SECRET=...
```

Estas credenciales viven en el panel de Auth0 bajo Applications → APIs → Auth0 Management API → Machine to Machine. Si en algún momento el comando `sincronizar_auth0` falla con "No se pudo obtener token", hay que verificar que estas dos variables estén presentes en el `.env` y que la aplicación M2M tenga los permisos `read:users` habilitados en Auth0.

---

## El problema de fondo: SQLite no es una base de datos compartida

SQLite es un archivo. Es excelente para desarrollo individual porque no requiere instalar ningún servidor de base de datos. Pero en proyectos con múltiples entornos o múltiples desarrolladores, su naturaleza de archivo local significa que cada entorno tiene su propia copia de los datos, desconectada del resto.

El workaround actual (`sincronizar_auth0`) resuelve el problema de los usuarios porque Auth0 actúa como fuente compartida de esa información. Pero los tickets, inasistencias, asignaciones y materiales no tienen esa fuente compartida: si Jordan crea 20 tickets en su entorno local, Moisés no los verá en su entorno aunque ejecute `sincronizar_auth0`.

---

## Recomendación a futuro: migrar a PostgreSQL en la nube

La solución definitiva para que todos los datos persistan entre entornos es usar una base de datos real que viva en un servidor accesible desde cualquier máquina. PostgreSQL es la opción estándar para proyectos Django en producción.

**Railway** es la opción más simple para este proyecto porque tiene plan gratuito, integración directa con GitHub, y el proceso de migración es mínimo. El proceso completo toma menos de una hora.

Para hacer la migración cuando el equipo esté listo, los pasos son:

Primero, crear una base de datos PostgreSQL en Railway desde su panel web. Railway entrega una variable de conexión en formato:

```
postgresql://usuario:contraseña@host:puerto/nombre_db
```

Luego instalar el driver de PostgreSQL en el proyecto:

```bash
pip install psycopg2-binary
```

Y agregar esa variable al `.env`:

```
DATABASE_URL=postgresql://usuario:contraseña@host:puerto/nombre_db
```

En `settings.py` reemplazar la configuración de SQLite por:

```python
import dj_database_url
import os

DATABASES = {
    'default': dj_database_url.config(
        default=os.getenv('DATABASE_URL'),
        conn_max_age=600,
    )
}
```

Instalar también:

```bash
pip install dj-database-url
```

Luego ejecutar las migraciones contra la nueva base de datos:

```bash
python manage.py migrate
python manage.py poblar_sistema
python manage.py crear_gestor --email gestor@duocuc.cl --rut TU_RUT --nombre Jordan --apellido Garcia
python manage.py sincronizar_auth0
```

A partir de ese momento todos los entornos que tengan la misma `DATABASE_URL` en su `.env` compartirán exactamente los mismos datos. Un ticket creado en el computador de Jordan aparece inmediatamente en el de Moisés o en el servidor de pruebas.

---

## Qué ocurre con los datos del proyecto si se migra a PostgreSQL

Al migrar, la BD local con los datos históricos (tickets, inasistencias, etc.) quedaría atrás. Si se quiere conservar esos datos hay que exportarlos primero con `python manage.py dumpdata > datos.json` y luego cargarlos en la nueva BD con `python manage.py loaddata datos.json`. Esto solo es relevante si ya hay datos de prueba valiosos que no se quieran perder.

---

## Resumen ejecutivo del problema y la solución

El login fallaba porque Auth0 autenticó correctamente la contraseña, pero la BD local SQLite no tenía ningún usuario registrado. La contraseña nunca fue el problema. La solución fue ejecutar `crear_gestor` para el usuario principal y luego `sincronizar_auth0` para importar todos los demás desde Auth0. Para que esto no vuelva a ocurrir en entornos nuevos, existe el procedimiento de 4 comandos documentado en esta sesión. Para que no vuelva a ocurrir nunca, la solución estructural es migrar a PostgreSQL compartido en la nube.
