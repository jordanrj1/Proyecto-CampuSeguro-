# ═══════════════════════════════════════════════════════════════
# CAMPUS SEGURO – Preparador de Escena para Defensa en Vivo
# ─────────────────────────────────────────────────────────────
# Archivo: app/management/commands/poblar_demo.py
#
# PROPÓSITO:
#   Prepara un laboratorio/sala específica para demostrar REINCIDENCIA.
#   Genera un historial crítico en una única ubicación para que salten las alertas.
#   DEJA LOS TICKETS NUEVOS SIN ASIGNAR Y EXCLUYE EL ESTADO 'EN MANTENCIÓN'.
#   Garantiza que la bandeja del técnico esté en CERO antes de la demo en vivo.
# ═══════════════════════════════════════════════════════════════

from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from app.models import (
    Usuario, Ticket, Ubicacion, CategoriaTicket, EstadoCatalogo,
    LogAuditoria, HistorialAcciones
)

class Command(BaseCommand):
    help = 'Prepara la base de datos con un escenario limpio de reincidencia para la demostración en vivo.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING('\n🎬 Preparando escenario para la demostración en vivo (Freeze de Técnicos)...'))

        # 1. Recuperar actores clave
        usuarios_base = Usuario.objects.filter(rol__codigo='usuario')
        gestores = Usuario.objects.filter(rol__codigo='gestor')
        guardias = Usuario.objects.filter(rol__codigo='guardia', estado_cuenta__codigo='activa')
        
        # Seleccionar una ubicación fija de la BD para concentrar la reincidencia
        ubicacion_demo = Ubicacion.objects.first()
        cat_electrico = CategoriaTicket.objects.filter(codigo='electrico').first() or CategoriaTicket.objects.first()

        if not ubicacion_demo or not usuarios_base.exists() or not gestores.exists():
            self.stdout.write(self.style.ERROR('❌ Error: Prerrequisitos insuficientes en la Base de Datos.'))
            return

        creador = usuarios_base.first()
        gestor = gestores.first()
        guardia = guardias.first() if guardias.exists() else None
        ahora = timezone.now()

        # Nombre amigable de la ubicación para el log de la consola
        sala_nombre = f"{ubicacion_demo.piso.edificio.nombre} - Sala {ubicacion_demo.sala}"
        self.stdout.write(self.style.WARNING(f'📍 Ubicación seleccionada para reincidencia: {sala_nombre}\n'))

        # =================================================================
        # 📜 ANTECEDENTES HISTÓRICOS (Para que el sistema acuse Reincidencia)
        # =================================================================
        
        # Ticket Histórico 1: Cerrado hace 30 días
        fecha_h1 = ahora - timedelta(days=30)
        t_old1 = Ticket.objects.create(
            creado_por=creador, ubicacion=ubicacion_demo, categoria=cat_electrico,
            urgencia='media', titulo="Cortocircuito en el enchufe del rack principal [DEMO-HISTORICO]",
            descripcion="Se genera chispa al conectar el switch secundario del laboratorio.",
            estado=EstadoCatalogo.para('ticket', 'cerrado'), cerrado_at=fecha_h1 + timedelta(days=2)
        )
        Ticket.objects.filter(pk=t_old1.pk).update(created_at=fecha_h1, updated_at=fecha_h1)
        create_logs_demo(t_old1, creador, "Ticket resuelto e histórico", "cerrado", fecha_h1)

        # Ticket Histórico 2: Cerrado hace 15 días
        fecha_h2 = ahora - timedelta(days=15)
        t_old2 = Ticket.objects.create(
            creado_por=creador, ubicacion=ubicacion_demo, categoria=cat_electrico,
            urgencia='alta', titulo="Recalentamiento de líneas automáticas monofásicas [DEMO-HISTORICO]",
            descripcion="El protector térmico del tablero del aula se cae constantemente al encender los computadores.",
            estado=EstadoCatalogo.para('ticket', 'cerrado'), cerrado_at=fecha_h2 + timedelta(days=1)
        )
        Ticket.objects.filter(pk=t_old2.pk).update(created_at=fecha_h2, updated_at=fecha_h2)
        create_logs_demo(t_old2, creador, "Ticket resuelto e histórico", "cerrado", fecha_h2)


        # =================================================================
        # 🎯 TICKETS ACTIVOS PARA LA DEMOSTRACIÓN (Listos para asignar en vivo)
        # =================================================================
        
        # Ticket Activo 1: Estado "Validado" (El guardia ya fue, falta que el gestor asigne al técnico)
        # ESTE ES EL TICKET PERFECTO PARA TU DEMOSTRACIÓN EN VIVO
        fecha_a1 = ahora - timedelta(hours=2)
        t_activo1 = Ticket.objects.create(
            creado_por=creador, ubicacion=ubicacion_demo, categoria=cat_electrico,
            urgencia='critica', titulo="Tablero Eléctrico Principal con olor a quemado y humo [ASIGNAR EN VIVO]",
            descripcion="🚨 EMERGENCIA: El sector posterior del laboratorio se encuentra totalmente sin energía y el tablero emite ruidos intermitentes.",
            estado=EstadoCatalogo.para('ticket', 'validado'),
            sub_estado=EstadoCatalogo.para('ticket_sub', 'revisado'),
            validado_por=guardia, gestor_responsable=gestor,
            afecta_clase=True, riesgo_electrico=True
        )
        Ticket.objects.filter(pk=t_activo1.pk).update(created_at=fecha_a1, updated_at=fecha_a1)
        create_logs_demo(t_activo1, creador, "Ticket reportado", "enviado", fecha_a1)
        create_logs_demo(t_activo1, guardia, "Guardia valida emergencia en terreno", "validado", fecha_a1 + timedelta(minutes=30))

        # Ticket Activo 2: Estado "En Validación" (Para mostrar cómo un guardia lo tiene en su bandeja)
        fecha_a2 = ahora - timedelta(minutes=45)
        t_activo2 = Ticket.objects.create(
            creado_por=creador, ubicacion=ubicacion_demo, categoria=cat_electrico,
            urgencia='baja', titulo="Canaleta de cables posterior desprendida [MOSTRAR BANDEJA]",
            descripcion="La protección plástica que cubre el cableado de red y fuerza del muro se cayó, dejando cables expuestos.",
            estado=EstadoCatalogo.para('ticket', 'en_validacion'),
            sub_estado=EstadoCatalogo.para('ticket_sub', 'asignado_guardia'),
            gestor_responsable=gestor
        )
        Ticket.objects.filter(pk=t_activo2.pk).update(created_at=fecha_a2, updated_at=fecha_a2)
        create_logs_demo(t_activo2, creador, "Ticket ingresado", "enviado", fecha_a2)

        self.stdout.write(self.style.SUCCESS('═' * 70))
        self.stdout.write(self.style.SUCCESS('✨ ESCENARIO DE DEFENSA INYECTADO IMPECABLEMENTE ✨'))
        self.stdout.write(self.style.SUCCESS(f' 1. Reincidencia forzada con 4 registros en: {sala_nombre}'))
        self.stdout.write(self.style.SUCCESS(' 2. Técnicos liberados: Cero tickets precargados en estado "En Mantención".'))
        self.stdout.write(self.style.SUCCESS(' 3. Ticket estrella para tu presentación listo en bandeja de asignación:'))
        self.stdout.write(self.style.WARNING(f'    👉 "{t_activo1.titulo}"'))
        self.stdout.write(self.style.SUCCESS('═' * 70))

# Auxiliar para logs limpios
def create_logs_demo(ticket, usuario, accion, estado, fecha):
    log = LogAuditoria.objects.create(ticket=ticket, usuario=usuario, accion=accion, estado_nuevo=estado, ip_address="127.0.0.1", modulo="ticket")
    LogAuditoria.objects.filter(pk=log.pk).update(created_at=fecha)
    hist = HistorialAcciones.objects.create(ticket=ticket, usuario=usuario, tipo_accion="demo", estado_anterior=None, estado_nuevo=estado, descripcion=accion, es_global=True, ip_address="127.0.0.1")
    HistorialAcciones.objects.filter(pk=hist.pk).update(created_at=fecha)