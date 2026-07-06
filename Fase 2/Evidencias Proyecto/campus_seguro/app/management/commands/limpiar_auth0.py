import requests
from django.core.management.base import BaseCommand
from django.conf import settings
import os

class Command(BaseCommand):
    help = 'Busca y elimina un usuario de Auth0 usando su correo institucional'

    def add_arguments(self, parser):
        parser.add_argument('--email', type=str, required=True, help='Correo del usuario a eliminar en Auth0')

    def handle(self, *args, **options):
        email = options['email'].strip()
        self.stdout.write(f"🔍 Buscando a '{email}' en los servidores de Auth0...")

        # 1. Obtener las configuraciones desde tu settings.py
        # Asegúrate de que estas variables apunten a tus llaves reales de Auth0
        domain = getattr(settings, 'AUTH0_DOMAIN', 'dev-0fnyqt3tlgffohdh.us.auth0.com')
        client_id = os.environ.get('AUTH0_MGMT_CLIENT_ID', '')
        client_secret = os.environ.get('AUTH0_MGMT_CLIENT_SECRET', '')

        if not client_id or not client_secret:
            self.stdout.write(self.style.ERROR("❌ Error: Faltan las credenciales AUTH0_MGMT_* en el archivo .env"))
            return

        # 2. Solicitar Token de Gestión (Management API Token)
        try:
            token_url = f"https://{domain}/oauth/token"
            token_payload = {
                "client_id": client_id,
                "client_secret": client_secret,
                "audience": f"https://{domain}/api/v2/",
                "grant_type": "client_credentials"
            }
            token_res = requests.post(token_url, json=token_payload, timeout=10)
            token_res.raise_for_status()
            access_token = token_res.json().get('access_token')
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Error al autenticar con la API de Auth0: {str(e)}"))
            return

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }

        # 3. Buscar al usuario por Email para obtener su ID interno de Auth0 (user_id)
        try:
            search_url = f"https://{domain}/api/v2/users-by-email"
            search_params = {"email": email}
            search_res = requests.get(search_url, headers=headers, params=search_params, timeout=10)
            search_res.raise_for_status()
            usuarios_encontrados = search_res.json()

            if not usuarios_encontrados:
                self.stdout.write(self.style.WARNING(f"⚠️  No se encontró ningún usuario con el correo {email} en Auth0."))
                return

            # Tomamos el primer registro que coincida
            user_id = usuarios_encontrados[0]['user_id']
            self.stdout.write(self.style.SUCCESS(f"🎯 Usuario encontrado. Auth0 ID: {user_id}"))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Error durante la búsqueda del email: {str(e)}"))
            return

        # 4. Enviar la orden de Eliminación Definitiva (DELETE)
        try:
            delete_url = f"https://{domain}/api/v2/users/{user_id}"
            delete_res = requests.delete(delete_url, headers=headers, timeout=10)
            
            if delete_res.status_code == 204:
                self.stdout.write(self.style.SUCCESS(f"🚀 ¡Éxito rotundo! El usuario '{email}' ha sido borrado permanentemente de Auth0."))
                self.stdout.write(self.style.NOTICE("💡 Ahora puedes volver a registrar este correo sin colisiones de duplicado."))
            else:
                self.stdout.write(self.style.ERROR(f"❌ Auth0 rechazó el borrado (Código {delete_res.status_code}): {delete_res.text}"))
                self.stdout.write(self.style.WARNING("💡 Consejo: Revisa si tu credencial M2M tiene el scope 'delete:users' activo."))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Error crítico en la solicitud de borrado: {str(e)}"))