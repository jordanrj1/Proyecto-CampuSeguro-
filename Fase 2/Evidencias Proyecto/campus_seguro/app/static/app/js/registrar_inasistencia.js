document.addEventListener("DOMContentLoaded", function() {
    const hoy = new Date().toLocaleDateString('sv-SE'); 
    const fechaDesde = document.getElementById('id_fecha_desde');
    const fechaHasta = document.getElementById('id_fecha_hasta');

    if (fechaDesde && fechaHasta) {
        fechaDesde.min = hoy;

        fechaDesde.addEventListener('change', function() {
            if (this.value < hoy) {
                this.value = hoy;
            }
            fechaHasta.min = this.value;
            if (fechaHasta.value && fechaHasta.value < this.value) {
                fechaHasta.value = this.value;
            }
        });

        fechaHasta.addEventListener('blur', function() {
            if (this.value && fechaDesde.value && this.value < fechaDesde.value) {
                alert("⚠ Error de lógica: La fecha de término no puede ser anterior a la fecha de inicio.");
                this.value = fechaDesde.value;
            }
        });
    }
});