from django.urls import path
from . import views

app_name = 'app'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('crear-ticket/', views.crear_ticket, name='crear_ticket'),
]