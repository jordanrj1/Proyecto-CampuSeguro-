function abrirModalTecnico(idTecnico) {
  const modal = document.getElementById('modal-tecnico-' + idTecnico);
  if (modal) modal.style.display = 'flex';
}

function cerrarModalTecnico(idTecnico) {
  const modal = document.getElementById('modal-tecnico-' + idTecnico);
  if (modal) modal.style.display = 'none';
}

function cambiarModalPestana(tecId, tab) {
  const secTickets = document.getElementById('modal-sec-tickets-' + tecId);
  const secInasistencias = document.getElementById('modal-sec-inasistencias-' + tecId);
  const btnTickets = document.getElementById('btn-tab-tk-' + tecId);
  const btnInasistencias = document.getElementById('btn-tab-in-' + tecId);
  
  if (tab === 'tickets') {
    if(secTickets) secTickets.style.display = 'block';
    if(secInasistencias) secInasistencias.style.display = 'none';
    if(btnTickets) btnTickets.className = 'btn btn-primary btn-sm';
    if(btnInasistencias) btnInasistencias.className = 'btn btn-ghost btn-sm';
  } else {
    if(secTickets) secTickets.style.display = 'none';
    if(secInasistencias) secInasistencias.style.display = 'block';
    if(btnTickets) btnTickets.className = 'btn btn-ghost btn-sm';
    if(btnInasistencias) btnInasistencias.className = 'btn btn-primary btn-sm';
  }
}