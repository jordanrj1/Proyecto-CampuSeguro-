# ═══════════════════════════════════════════════════════════════
# CAMPUS SEGURO – Simulador Transaccional de Carga Operativa
# ─────────────────────────────────────────────────────────────
# Archivo: app/management/commands/poblar_tickets.py
#
# PROPÓSITO:
#   Genera 25 tickets con historias clínicas realistas distribuidas en 3 meses.
#   Cada ticket avanza orgánicamente por la máquina de estados simulando la
#   intervención de usuarios base, gestores, guardias y técnicos de mantención.
#   Se enfoca exclusivamente en los 7 estados clave seleccionados.
# ═══════════════════════════════════════════════════════════════

import random
from datetime import timedelta
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils import timezone
from app.models import (
    Usuario, Ticket, Ubicacion, CategoriaTicket, Material, EstadoCatalogo,
    AsignacionTicket, ValidacionGuardia, SesionTrabajo, MaterialUtilizado,
    RegistroMantencion, NoReparable, HistorialAcciones, LogAuditoria
)

# Pool de datos contextuales para reportes realistas según categoría
POOL_INCIDENCIAS = {
    'electrico': [
        ("Enchufe quemado con chispas", "El enchufe posterior del aula presenta signos de cortocircuito y olor a plástico quemado al conectar equipos."),
        ("Luminaria parpadea constantemente", "Tubos fluorescentes parpadean intermitentemente causando molestia visual durante el desarrollo de clases."),
        ("Extractor de aire no enciende", "El extractor del baño se encuentra inoperante, acumula humedad y genera ruidos extraños en el tablero secundario.")
    ],
    'plomeria': [
        ("Filtración severa en lavamanos", "Gotera constante en la cañería de abasto inferior inundando parte del piso y generando riesgo de resbalones."),
        ("Inodoro tapado con rebose", "WC obstruido presenta retorno de agua al descargar, requiere descompresión e higienización urgente de la zona."),
        ("Llave de paso agripada", "No es posible cortar el paso de agua del módulo debido a acumulación de sarro y óxido en la válvula principal.")
    ],
    'infraestructura': [
        ("Puerta de acceso trabada", "La cerradura magnética o pomo se encuentra desalineado, impidiendo el ingreso fluido de alumnos al laboratorio."),
        ("Vidrio trizado en ventanal", "Ventanal del costado izquierdo presenta fisura por impacto de viento. Riesgo de desprendimiento de astillas."),
        ("Tabiquería de yeso rota", "Agujero en el muro de vulcanita por golpe de mobiliario. Requiere enyesado, lijado y pintura de terminación.")
    ],
    'tecnologia': [
        ("Proyector multimedia no da señal", "Equipo colgado al techo enciende pero no reconoce entradas HDMI ni VGA de la mesa docente."),
        ("Punto de red RJ45 desconectado", "Roseta de red de la pared no entrega direccionamiento IP dinámico al computador del laboratorio."),
        ("Gabinete Rack sin energía", "La PDU interior del rack secundario no energiza los switches del nivel, dejando sin señal WiFi al pasillo completo.")
    ]
}

class Command(BaseCommand):
    help = 'Genera 25 tickets realistas enfocados exclusivamente en los 7 estados clave del ERP.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING('\n🚀 Iniciando Simulación del Historial de Tickets (Últimos 3 Meses)...'))

        # 🗄️ Ingesta nativa de entidades de la base de datos
        usuarios_base = list(Usuario.objects.filter(rol__codigo='usuario'))
        gestores = list(Usuario.objects.filter(rol__codigo='gestor'))
        guardias = list(Usuario.objects.filter(rol__codigo='guardia', estado_cuenta__codigo='activa'))
        tecnicos = list(Usuario.objects.filter(rol__codigo='mantencion', estado_cuenta__codigo='activa'))
        ubicaciones = list(Ubicacion.objects.all())
        categorias = list(CategoriaTicket.objects.filter(activo=True))
        materiales = list(Material.objects.filter(activo=True))

        # Failsafe de validación de prerequisitos maestros
        if not usuarios_base or not gestores or not guardias or not tecnicos or not ubicaciones or not categorias:
            self.stdout.write(self.style.ERROR('❌ Error: Debes ejecutar primero "python manage.py poblar_sistema" y tener usuarios creados con los roles correspondientes.'))
            return

        # 🌟 DISTRIBUCIÓN EXACTA DE TUS 7 ESTADOS PARA LOS 25 TICKETS
        estados_finales = (
            ['enviado'] * 3 +        # 3 tickets nuevos en bandeja
            ['en_validacion'] * 3 +  # 3 tickets asignados a un guardia en terreno
            ['validado'] * 3 +       # 3 tickets aprobados por guardia esperando técnico
            ['en_mantencion'] * 4 +  # 4 tickets en reparación activa por el técnico
            ['no_reparado'] * 3 +    # 3 tickets que el técnico descartó por falta de solución
            ['reparado'] * 4 +       # 4 tickets terminados esperando firma del gestor
            ['cerrado'] * 5          # 5 tickets históricos resueltos con acta de conformidad
        )
        random.shuffle(estados_finales)

        tickets_creados = 0

        for i in range(25):
            estado_objetivo = estados_finales[i]
            
            # 📅 1. Generación de línea de tiempo analítica (Fecha de creación aleatoria en los últimos 90 días)
            ahora = timezone.now()
            dias_atras = random.randint(3, 90)
            fecha_ticket = ahora - timedelta(days=dias_atras, hours=random.randint(1, 23), minutes=random.randint(1, 59))
            
            # Selección aleatoria de emisores e infraestructura
            creador = random.choice(usuarios_base)
            gestor = random.choice(gestores)
            guardia = random.choice(guardias)
            tecnico = random.choice(tecnicos)
            ubicacion = random.choice(ubicaciones)
            cat = random.choice(categorias)
            urgencia = random.choice(['baja', 'media', 'alta', 'critica'])

            # Extraer títulos lógicos según la categoría seleccionada
            pool = POOL_INCIDENCIAS.get(cat.codigo, POOL_INCIDENCIAS['infraestructura'])
            titulo, descripcion = random.choice(pool)
            if Ticket.objects.filter(titulo=f"{titulo} #{i+1}").exists():
                continue

            # 🛠️ PASO 1: Creación del Ticket Base (Estado: Enviado)
            ticket = Ticket.objects.create(
                creado_por=creador,
                ubicacion=ubicacion,
                categoria=cat,
                urgencia=urgencia,
                titulo=f"{titulo} #{i+1}",
                descripcion=descripcion,
                estado=EstadoCatalogo.para('ticket', 'enviado'),
                afecta_clase=random.choice([True, False]),
                riesgo_electrico=(cat.codigo == 'electrico'),
                riesgo_estructural=(cat.codigo == 'infraestructura'),
                id_activo_sap=f"SAP-2026-{random.randint(1000, 9999)}" if random.choice([True, False]) else None
            )
            # Forzar fecha de creación retroactiva para simular historia
            Ticket.objects.filter(pk=ticket.pk).update(created_at=fecha_ticket, updated_at=fecha_ticket)
            
            # Trazabilidad inicial
            create_audit_log(ticket, creador, 'Ticket creado', 'enviado', fecha_ticket)
            create_historial(ticket, creador, 'creacion', None, 'enviado', f'Ticket creado por {creador.get_full_name()}', fecha_ticket)

            # Si el objetivo era solo "enviado", pasamos al siguiente ticket
            if estado_objetivo == 'enviado':
                tickets_creados += 1
                continue

            # 🛡️ PASO 2: Avance a Validación de Guardia
            fecha_validacion_asig = fecha_ticket + timedelta(hours=random.randint(1, 4))
            AsignacionTicket.objects.create(
                ticket=ticket, usuario=guardia, rol_asignacion='guardia', asignado_por=gestor,
                estado=EstadoCatalogo.para('asignacion', 'completada' if estado_objetivo != 'en_validacion' else 'pendiente'),
                fecha_asignacion=fecha_validacion_asig, fecha_programada=fecha_validacion_asig.date(),
                fecha_completado=fecha_validacion_asig + timedelta(minutes=45) if estado_objetivo != 'en_validacion' else None
            )
            
            ticket.estado = EstadoCatalogo.para('ticket', 'en_validacion')
            ticket.sub_estado = EstadoCatalogo.para('ticket_sub', 'asignado_guardia')
            ticket.gestor_responsable = gestor
            ticket.save()
            Ticket.objects.filter(pk=ticket.pk).update(updated_at=fecha_validacion_asig)

            create_audit_log(ticket, gestor, f'Asignado a guardia {guardia.get_full_name()}', 'en_validacion', fecha_validacion_asig)
            create_historial(ticket, gestor, 'asignacion', 'enviado', 'en_validacion', f'Ticket derivado a guardia para inspección.', fecha_validacion_asig)

            if estado_objetivo == 'en_validacion':
                tickets_creados += 1
                continue

            # Realizar inspección de terreno (Guardia valida el ticket)
            fecha_inspeccion = fecha_validacion_asig + timedelta(minutes=40)
            ValidacionGuardia.objects.create(
                ticket=ticket, guardia=guardia, resultado='valido',
                comentario="Se constata en terreno la gravedad de la falla reportada. Coincide con la descripción.",
                checklist_electrico=(cat.codigo == 'electrico'), checklist_estructural=(cat.codigo == 'infraestructura'),
                checklist_accesibilidad=ticket.afecta_clase, tiempo_validacion_minutos=15
            )
            ValidacionGuardia.objects.filter(ticket=ticket).update(created_at=fecha_inspeccion)

            ticket.estado = EstadoCatalogo.para('ticket', 'validado')
            ticket.sub_estado = EstadoCatalogo.para('ticket_sub', 'revisado')
            ticket.save()
            Ticket.objects.filter(pk=ticket.pk).update(updated_at=fecha_inspeccion)

            create_audit_log(ticket, guardia, 'Validación aprobada en terreno', 'validado', fecha_inspeccion)
            create_historial(ticket, guardia, 'validacion', 'en_validacion', 'validado', 'Guardia confirma reporte válido en terreno.', fecha_inspeccion)

            if estado_objetivo == 'validado':
                tickets_creados += 1
                continue

            # 🔧 PASO 3: Derivación e Inicio de Trabajos (Mantención)
            fecha_mant_asig = fecha_inspeccion + timedelta(hours=random.randint(2, 6))
            AsignacionTicket.objects.create(
                ticket=ticket, usuario=tecnico, rol_asignacion='mantencion', asignado_por=gestor,
                estado=EstadoCatalogo.para('asignacion', 'activa' if estado_objetivo == 'en_mantencion' else 'completada'),
                fecha_asignacion=fecha_mant_asig, fecha_programada=fecha_mant_asig.date(),
                tiempo_estimado=Decimal(random.choice(['1.5', '2.0', '3.5'])),
                diagnostico_preliminar="Se requiere intervención con herramientas manuales e insumos del pañol central.",
                fecha_completado=fecha_mant_asig + timedelta(days=1) if estado_objetivo not in ['en_mantencion'] else None
            )

            ticket.estado = EstadoCatalogo.para('ticket', 'en_mantencion')
            ticket.sub_estado = EstadoCatalogo.para('ticket_sub', 'asignado_tecnico')
            ticket.asignado_a = tecnico
            ticket.inicio_trabajo_at = fecha_mant_asig + timedelta(minutes=30)
            ticket.save()
            Ticket.objects.filter(pk=ticket.pk).update(updated_at=fecha_mant_asig)

            create_audit_log(ticket, gestor, f'Asignado a técnico {tecnico.get_full_name()}', 'en_mantencion', fecha_mant_asig)
            create_historial(ticket, gestor, 'asignacion', 'validado', 'en_mantencion', f'Orden de trabajo emitida para técnico.', fecha_mant_asig)

            if estado_objetivo == 'en_mantencion':
                tickets_creados += 1
                continue

            # ⏱️ PASO 4: Registro de Avances y Consumo Logístico (Sesiones de Trabajo)
            fecha_sesion = ticket.inicio_trabajo_at + timedelta(hours=random.randint(1, 3))
            sesion = SesionTrabajo.objects.create(
                ticket=ticket, tecnico=tecnico, inicio=ticket.inicio_trabajo_at, fin=fecha_sesion,
                horas_hombre=Decimal(random.choice(['1.0', '2.5', '3.0'])),
                descripcion_avance="Despliegue en terreno, desarme de componentes dañados y limpieza del área física.",
                herramientas_utilizadas="Destornilladores, multímetro, alicate de presión.",
                tipo_cierre='completado' if estado_objetivo in ['reparado', 'cerrado'] else 'fin_turno',
                progreso=100 if estado_objetivo in ['reparado', 'cerrado'] else 50
            )
            SesionTrabajo.objects.filter(pk=sesion.pk).update(created_at=fecha_sesion)

            # Consumo logístico de materiales del pañol
            material_gastado = random.choice(materiales)
            MaterialUtilizado.objects.create(
                sesion_trabajo=sesion, material=material_gastado,
                cantidad_utilizada=Decimal(random.randint(1, 4)),
                observacion="Material utilizado para la reparación física directa."
            )

            create_audit_log(ticket, tecnico, 'Avance de jornada registrado', 'en_mantencion', fecha_sesion)

            # 🏁 PASO 5: Cierre de Técnico (Bifurcación Reparado vs No Reparado)
            fecha_reparado = fecha_sesion + timedelta(minutes=15)
            
            if estado_objetivo == 'no_reparado':
                NoReparable.objects.create(
                    ticket=ticket, tecnico=tecnico,
                    motivo_tecnico="Falla estructural interna severa. Requiere evaluación de proveedor externo o recambio completo del equipo.",
                    material_requerido="Repuesto matriz industrial no disponible en pañol.",
                    criticidad="alta"
                )
                NoReparable.objects.filter(ticket=ticket).update(created_at=fecha_reparado)
                
                ticket.estado = EstadoCatalogo.para('ticket', 'no_reparado')
                ticket.sub_estado = None
                ticket.inicio_trabajo_at = None
                ticket.save()
                Ticket.objects.filter(pk=ticket.pk).update(updated_at=fecha_reparado)

                create_audit_log(ticket, tecnico, 'Marcado como No Reparable', 'no_reparado', fecha_reparado)
                create_historial(ticket, tecnico, 'no_reparable', 'en_mantencion', 'no_reparado', 'Técnico declara el ticket como No Reparable.', fecha_reparado)
                
                tickets_creados += 1
                continue
                
            else:
                RegistroMantencion.objects.create(
                    ticket=ticket, tecnico=tecnico,
                    causa_raiz=f"Desgaste natural de componentes asociados a la categoría {cat.nombre_display}.",
                    fecha_registro=fecha_reparado
                )
                ticket.estado = EstadoCatalogo.para('ticket', 'reparado')
                ticket.sub_estado = None
                ticket.inicio_trabajo_at = None
                ticket.save()
                Ticket.objects.filter(pk=ticket.pk).update(updated_at=fecha_reparado)

                create_audit_log(ticket, tecnico, 'Reparación finalizada con éxito', 'reparado', fecha_reparado)
                create_historial(ticket, tecnico, 'completar_mantencion', 'en_mantencion', 'reparado', 'Técnico declara reparación finalizada.', fecha_reparado)

            if estado_objetivo == 'reparado':
                tickets_creados += 1
                continue

            # 🔒 PASO 6: Aprobación de Gestor (Estado: Cerrado)
            fecha_cierre = fecha_reparado + timedelta(hours=random.randint(1, 24))
            
            ticket.estado = EstadoCatalogo.para('ticket', 'cerrado')
            ticket.cerrado_at = fecha_cierre
            ticket.save()
            Ticket.objects.filter(pk=ticket.pk).update(updated_at=fecha_cierre)

            create_audit_log(ticket, gestor, 'Reparación aprobada por gestor — ticket cerrado', 'cerrado', fecha_cierre)
            create_historial(ticket, gestor, 'cierre', 'reparado', 'cerrado', 'Gestor aprueba cierre conforme técnico.', fecha_cierre)

            tickets_creados += 1

        self.stdout.write(self.style.SUCCESS(f'\n✨ Simulación finalizada correctamente. Se inyectaron {tickets_creados} tickets históricos con trazabilidad relacional completa en MySQL.'))

# ── FUNCIONES DE APOYO / AYUDANTES ──
def create_audit_log(ticket, usuario, accion, estado_nuevo, fecha):
    log = LogAuditoria.objects.create(
        ticket=ticket, usuario=usuario, accion=accion,
        estado_nuevo=estado_nuevo, ip_address="10.240.12.8", modulo="ticket"
    )
    LogAuditoria.objects.filter(pk=log.pk).update(created_at=fecha)

def create_historial(ticket, usuario, tipo, est_ant, est_nue, desc, fecha):
    hist = HistorialAcciones.objects.create(
        ticket=ticket, usuario=usuario, tipo_accion=tipo,
        estado_anterior=est_ant, estado_nuevo=est_nue,
        descripcion=desc, es_global=True, ip_address="10.240.12.8"
    )
    HistorialAcciones.objects.filter(pk=hist.pk).update(created_at=fecha)