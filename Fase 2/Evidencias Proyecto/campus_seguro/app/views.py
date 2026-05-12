from django.shortcuts import render
from django.contrib.auth.decorators import login_required

"@login_required"
def dashboard(request):
    """Vista del dashboard - Gestión de Tickets"""
    return render(request, 'app/dashboard.html')

"@login_required"
def crear_ticket(request):
    """Vista para crear nuevo ticket"""
    return render(request, 'app/crear_ticket.html')

def gestor_tickets(request):
    return render(request, 'app/gestor_tickets.html')

def gestor_dashboard(request):
    return render(request, 'app/gestor_dashboard.html')