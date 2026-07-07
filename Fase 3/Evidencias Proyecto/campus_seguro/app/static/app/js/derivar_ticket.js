// static/app/js/derivar_ticket.js
document.addEventListener("DOMContentLoaded", function() {
    // 1. Obtener la fecha de hoy en formato YYYY-MM-DD
    const hoy = new Date().toLocaleDateString('sv-SE');
    
    const fechaValidacion = document.getElementById("fechaValidacion");
    const fechaMantencion = document.getElementById("fechaMantencion");

    // 🚀 ¡AQUÍ ESTÁ EL TRUCO! Forzamos el bloqueo visual apenas carga la página
    if (fechaValidacion) fechaValidacion.min = hoy; // Pone el calendario del guardia en gris hacia atrás
    if (fechaMantencion) fechaMantencion.min = hoy; // Pone el calendario del técnico en gris hacia atrás


    // El resto de tu código "blur" se queda exactamente igual abajo...
    if (fechaValidacion) {
        fechaValidacion.addEventListener("blur", function() {
            if (this.value && this.value < hoy) {
                alert("⚠ No puedes seleccionar una fecha pasada para la validación.");
                this.value = hoy;
                this.dispatchEvent(new Event('change'));
            }
        });
    }

    if (fechaMantencion) {
        fechaMantencion.addEventListener("blur", function() {
            if (this.value && this.value < hoy) {
                alert("⚠ No puedes seleccionar una fecha pasada para la mantención.");
                this.value = hoy;
                this.dispatchEvent(new Event('change'));
            }
        });
    }
});