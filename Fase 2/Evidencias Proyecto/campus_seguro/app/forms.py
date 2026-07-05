import re
from django import forms
from django.core.exceptions import ValidationError
from django.forms import inlineformset_factory
from .models import (
    AsignacionTicket, SesionTrabajo, Usuario, Ticket, ValidacionGuardia, RegistroMantencion,
    MaterialUtilizado, Material, NoReparable, Inasistencia, MaterialesFaltantes,
    EstadoCatalogo
)


# ═══════════════════════════════════════════════════════════════
# AUTENTICACIÓN
# ─────────────────────────────────────────────────────────────
# Formularios relacionados con el flujo de autenticación:
# login, registro, recuperación de contraseña.
#
# CAMBIO vs. versión anterior:
#   - RegistroUsuarioForm ya NO tiene campo 'rol' (siempre = 'usuario').
#     El gestor asigna el rol al aprobar la cuenta desde su panel.
#   - RegistroUsuarioForm usa set_unusable_password() cuando Auth0
#     está habilitado (la contraseña real se guarda en Auth0, no aquí).
#   - Se agrega AsignarRolForm: formulario que usa el gestor en la
#     vista aprobar_cuenta() para asignar rol al momento de activar cuenta.
# ═══════════════════════════════════════════════════════════════
class LoginForm(forms.Form):
    """
    Formulario de inicio de sesión.

    Campos:
        username: Acepta username O correo institucional.
                  views.py resuelve cuál es antes de autenticar.
        password: Contraseña. Se envía a Auth0 si está configurado,
                  o a Django authenticate() en modo local/fallback.
        recordar: "Mantener sesión". Si es False, la sesión expira
                  al cerrar el navegador (session.set_expiry(0)).

    Conexión: Usado en views.login_view().
    """
    username = forms.CharField(
        label='Usuario o Correo Institucional',
        max_length=150,
        widget=forms.TextInput(attrs={
            'placeholder': 'usuario@duoc.cl',
            'autofocus': True,
        }),
    )
    password = forms.CharField(
        label='Contraseña',
        widget=forms.PasswordInput(attrs={'placeholder': '••••••••'}),
    )
    recordar = forms.BooleanField(label='Mantener sesión iniciada', required=False)


class RegistroUsuarioForm(forms.ModelForm):
    """
    Formulario de solicitud de cuenta nueva.

    FLUJO POST-REGISTRO:
        1. Usuario completa este formulario.
        2. Si Auth0 está habilitado:
           - save() llama a auth0_service.crear_usuario_auth0() para
             registrar al usuario en Auth0 con su contraseña.
           - set_unusable_password() en el modelo local → contraseña
             NO se guarda en la BD de Campus Seguro.
           - Se guarda auth0_sub (ID de Auth0) en el modelo local.
        3. Si Auth0 NO está habilitado (modo desarrollo/fallback):
           - set_password() guarda la contraseña hasheada localmente.
           - auth0_sub queda en None.
        4. En ambos casos: rol='usuario', estado='pendiente'.
        5. El gestor revisa y aprueba (o rechaza) desde su panel.

    CAMBIO CLAVE:
        El campo 'rol' fue ELIMINADO del formulario. Todos los registros
        automáticamente tienen rol='usuario'. El gestor asigna el rol
        real al aprobar la cuenta (ver AsignarRolForm).

    Campos:
        first_name, last_name: Nombre completo del solicitante.
        rut: RUT chileno (validado como único en el sistema).
        correo_institucional: Correo @duoc.cl (único, usado como username).
        telefono: Opcional.
        vinculo: Alumno / Docente / Administrativo / Funcionario.
        carrera, jornada, sede: Datos académicos del usuario base.
        password1, password2: Contraseña (validada, enviada a Auth0 si aplica).
        acepta_terminos: Checkbox obligatorio de políticas de uso.

    Conexión: Usado en views.registro_view().
    """
    password1 = forms.CharField(
        label='Contraseña',
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Ej: Campus2024!',
            'id': 'id_password1',
        }),
        min_length=8,
    )
    password2 = forms.CharField(
        label='Confirmar Contraseña',
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Repite la contraseña',
            'id': 'id_password2',
        }),
    )
    acepta_terminos = forms.BooleanField(
        label='Acepto las políticas de uso institucional',
        required=True,
    )

    class Meta:
        model = Usuario
        fields = [
            'first_name', 'last_name', 'rut', 'correo_institucional',
            'telefono',
            'vinculo', 'carrera', 'jornada', 'sede',
        ]
        widgets = {
            'first_name': forms.TextInput(attrs={'placeholder': 'Juan'}),
            'last_name': forms.TextInput(attrs={'placeholder': 'Pérez González'}),
            'rut': forms.TextInput(attrs={'placeholder': '12.345.678-9'}),
            'correo_institucional': forms.EmailInput(attrs={'placeholder': 'tu.correo@duoc.cl'}),
            'telefono': forms.TextInput(attrs={'placeholder': '+56 9 1234 5678'}),
            'carrera': forms.Select(attrs={'id': 'carreraSelect'}),
        }

    def clean_password1(self):
        """
        Valida que la contraseña cumpla la política de Auth0 (política 'Good'):
        mínimo 8 caracteres con al menos 3 de los 4 grupos: minúsculas,
        mayúsculas, números y caracteres especiales.
        Esto evita que Auth0 rechace la contraseña con PasswordStrengthError
        antes de mostrarle el error al usuario.
        """
        password = self.cleaned_data.get('password1', '')
        grupos = [
            bool(re.search(r'[a-z]', password)),
            bool(re.search(r'[A-Z]', password)),
            bool(re.search(r'\d', password)),
            bool(re.search(r'[^a-zA-Z0-9]', password)),
        ]
        if sum(grupos) < 3:
            raise ValidationError(
                'La contraseña debe incluir al menos 3 de estos 4 grupos: '
                'minúsculas, MAYÚSCULAS, números (123) y especiales (!@#$). '
                'Ejemplo válido: Campus2024!'
            )
        return password

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('password1') != cleaned.get('password2'):
            raise ValidationError('Las contraseñas no coinciden.')
        return cleaned

    def clean_correo_institucional(self):
        correo = self.cleaned_data['correo_institucional'].lower().strip()
        if Usuario.objects.filter(correo_institucional__iexact=correo).exists():
            raise ValidationError('Este correo ya está registrado.')
        return correo

    def clean_rut(self):
        rut_raw = self.cleaned_data['rut'].strip()
        rut = rut_raw.replace('.', '').replace('-', '').replace(' ', '').upper()
        # 7-9 dígitos de cuerpo + 1 dígito verificador (K o 0-9)
        if not re.match(r'^\d{7,9}[0-9K]$', rut):
            raise ValidationError('RUT inválido. Ingrese entre 7 y 9 dígitos seguidos del dígito verificador, ej: 12.345.678-9.')
        cuerpo, dv = rut[:-1], rut[-1]
        suma, mult = 0, 2
        for c in reversed(cuerpo):
            suma += int(c) * mult
            mult = mult + 1 if mult < 7 else 2  # ciclo: 2-3-4-5-6-7-2-3...
        resto = 11 - (suma % 11)
        dv_esperado = '0' if resto == 11 else 'K' if resto == 10 else str(resto)
        if dv != dv_esperado:
            raise ValidationError(f'Dígito verificador incorrecto. El correcto es -{dv_esperado}.')
        if Usuario.objects.filter(rut__iexact=rut).exists():
            raise ValidationError('Este RUT ya está registrado.')
        # Guardar siempre en formato XX.XXX.XXX-D (con puntos y guión)
        cuerpo_fmt = re.sub(r'(?<=\d)(?=(\d{3})+$)', '.', cuerpo)
        return f'{cuerpo_fmt}-{dv}'

    def clean_telefono(self):
        telefono = self.cleaned_data.get('telefono', '').strip()
        if telefono and not re.match(r'^[\d\s\+\-\(\)]+$', telefono):
            raise ValidationError('El teléfono solo puede contener dígitos, espacios y los caracteres +, -, ().')
        return telefono

    def save(self, commit=True, auth0_sub=None, usar_auth0=False):
        """
        Guarda el usuario en la BD local.

        Parámetros:
            commit (bool): Si True, ejecuta .save() en la BD.
            auth0_sub (str|None): ID de Auth0 si el usuario ya fue creado
                                  allá. Se almacena en Usuario.auth0_sub.
            usar_auth0 (bool): Si True, aplica set_unusable_password()
                               (la contraseña real está en Auth0, no aquí).

        Rol siempre 'usuario': El rol real lo asigna el gestor al aprobar.
        Estado siempre 'pendiente': Requiere aprobación del gestor.
        is_active=False: El usuario no puede hacer login hasta que el
                         gestor lo apruebe y cambie is_active=True.
        """
        user = super().save(commit=False)
        user.username = self.cleaned_data['correo_institucional']
        user.email = self.cleaned_data['correo_institucional']
        user.rol = 'usuario'  # Siempre usuario al registrarse; gestor asigna rol real
        user.estado_cuenta = EstadoCatalogo.para('cuenta', 'pendiente')
        user.is_active = False  # Inactivo hasta aprobación del gestor

        if usar_auth0 and auth0_sub:
            # Auth0 guarda la contraseña → no la guardamos localmente
            user.set_unusable_password()
            user.auth0_sub = auth0_sub
        else:
            # Modo fallback (desarrollo sin Auth0): guardar localmente
            user.set_password(self.cleaned_data['password1'])

        if commit:
            user.save()
        return user


class AsignarRolForm(forms.Form):
    """
    Formulario para que el gestor asigne un rol al aprobar una cuenta.

    Aparece en la vista aprobar_cuenta() → template revisar_cuenta.html.
    El gestor selecciona el rol que tendrá el usuario y luego hace clic
    en "Aprobar". El rol se guarda en Usuario.rol y se sincroniza con
    Auth0 via auth0_service.actualizar_rol_auth0().

    Roles disponibles para asignar (excluye 'usuario' porque es el default
    de registro; el gestor solo necesita promover a roles operativos):
        - usuario: Sin cambio de rol (alumno, docente, etc.)
        - gestor: Supervisor del sistema
        - guardia: Validación en terreno
        - mantencion: Reparaciones y mantención

    Conexión: Usado en views.aprobar_cuenta().
    """
    ROL_CHOICES = [
        ('usuario', 'Usuario Base (alumno, docente, administrativo)'),
        ('gestor', 'Gestor – Supervisión y control'),
        ('guardia', 'Guardia – Validación en terreno'),
        ('mantencion', 'Mantención – Reparaciones'),
    ]

    rol = forms.ChoiceField(
        choices=ROL_CHOICES,
        label='Rol a asignar',
        initial='usuario',
        widget=forms.Select(attrs={'class': 'form-control'}),
    )


class OlvideContrasenaForm(forms.Form):
    correo = forms.EmailField(
        label='Correo institucional',
        widget=forms.EmailInput(attrs={'placeholder': 'tu.correo@duoc.cl', 'autofocus': True}),
    )


class RestablecerContrasenaForm(forms.Form):
    password1 = forms.CharField(
        label='Nueva contraseña',
        widget=forms.PasswordInput(attrs={'placeholder': 'Mínimo 8 caracteres'}),
        min_length=8,
    )
    password2 = forms.CharField(
        label='Confirmar nueva contraseña',
        widget=forms.PasswordInput(attrs={'placeholder': 'Repite la contraseña'}),
    )

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('password1') != cleaned.get('password2'):
            raise ValidationError('Las contraseñas no coinciden.')
        return cleaned


# ═══════════════════════════════════════════════════════════════
# TICKETS
# ═══════════════════════════════════════════════════════════════
class TicketForm(forms.ModelForm):
    """
    Formulario para crear/editar tickets de reporte de incidencia.
    
    ✅ CAMBIO CLAVE: Se sobrescribe __init__ para que:
    - El campo 'urgencia' NO tenga valor por defecto (muestra "Seleccionar...")
    - El campo 'categoria' NO tenga valor por defecto
    - Los campos tengan clases CSS de Bootstrap para el template
    """
    class Meta:
        model = Ticket
        fields = [
            'titulo', 'ubicacion',
            'categoria', 'urgencia', 'descripcion',
            'afecta_clase', 'riesgo_electrico', 'riesgo_estructural', 'riesgo_accesibilidad',
            'foto_evidencia', 'id_activo_sap',
        ]
        widgets = {
            'titulo': forms.TextInput(attrs={
                'placeholder': 'Ej: Enchufe quemado en sala 305',
                'class': 'form-control',
            }),
            'descripcion': forms.Textarea(attrs={
                'rows': 4,
                'placeholder': 'Describe el problema, síntomas y contexto...',
                'class': 'form-control',
            }),
            'ubicacion': forms.Select(attrs={'class': 'form-select'}),
            'categoria': forms.Select(attrs={'class': 'form-select'}),
            'urgencia': forms.Select(attrs={'class': 'form-select'}),
            'afecta_clase': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'riesgo_electrico': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'riesgo_estructural': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'riesgo_accesibilidad': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'foto_evidencia': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*',
            }),
            'id_activo_sap': forms.TextInput(attrs={
                'placeholder': 'ACT-2024-001 (opcional)',
                'class': 'form-control',
            }),
        }

    def __init__(self, *args, **kwargs):
        """
        ✅ CAMBIO CLAVE: Elimina el valor por defecto de 'urgencia' y 'categoria'
        para que el template muestre "Seleccionar..." en lugar de "Media".
        
        El modelo Ticket tiene default='media' en urgencia, lo que hace que
        Django Form lo preseleccione. Aquí lo forzamos a vacío.
        """
        super().__init__(*args, **kwargs)
        
        # ✅ Quitar el default de urgencia (que viene del modelo como 'media')
        self.fields['urgencia'].initial = ''
        self.fields['urgencia'].required = True
        self.fields['urgencia'].empty_label = 'Seleccionar...'
        
        # ✅ Quitar el default de categoria por consistencia
        self.fields['categoria'].initial = ''
        self.fields['categoria'].required = True
        self.fields['categoria'].empty_label = 'Seleccionar...'
        
        # Agregar labels más amigables
        self.fields['titulo'].label = 'Título del reporte'
        self.fields['descripcion'].label = 'Descripción detallada'
        self.fields['ubicacion'].label = 'Ubicación'
        self.fields['categoria'].label = 'Categoría'
        self.fields['urgencia'].label = 'Urgencia'
        self.fields['foto_evidencia'].label = 'Evidencia fotográfica'
        self.fields['afecta_clase'].label = 'Afecta clases'
        self.fields['riesgo_electrico'].label = 'Riesgo eléctrico'
        self.fields['riesgo_estructural'].label = 'Riesgo estructural'
        self.fields['riesgo_accesibilidad'].label = 'Afecta accesibilidad'

    def clean_foto_evidencia(self):
        """Valida que la foto sea obligatoria al crear un ticket nuevo."""
        foto = self.cleaned_data.get('foto_evidencia')
        if not foto and not self.instance.pk:
            raise ValidationError('La foto de evidencia es obligatoria.')
        
        # Validar tamaño (10MB máximo)
        if foto and foto.size > 10 * 1024 * 1024:
            raise ValidationError('La foto no puede superar los 10 MB.')
        
        return foto


# ═══════════════════════════════════════════════════════════════
# VALIDACIÓN GUARDIA
# ═══════════════════════════════════════════════════════════════
class ValidacionForm(forms.ModelForm):
    class Meta:
        model = ValidacionGuardia
        fields = ['resultado', 'comentario', 'foto_evidencia',
                  'checklist_electrico', 'checklist_estructural', 'checklist_accesibilidad']
        widgets = {
            'resultado': forms.RadioSelect(choices=ValidacionGuardia.RESULTADO_CHOICES),
            'comentario': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Detalle del resultado de la validación'}),
            'foto_evidencia': forms.FileInput(attrs={'accept': 'image/*'}),
        }

    def clean(self):
        cleaned = super().clean()
        foto_nueva = cleaned.get('foto_evidencia')
        foto_existente = self.instance.foto_evidencia if self.instance and self.instance.pk else None
        if not foto_nueva and not foto_existente:
            raise ValidationError('La evidencia fotográfica es obligatoria.')
        if not cleaned.get('comentario'):
            raise ValidationError('El comentario es obligatorio.')
        return cleaned


# ═══════════════════════════════════════════════════════════════
# MANTENCIÓN
# ═══════════════════════════════════════════════════════════════
class MantencionForm(forms.ModelForm):
    class Meta:
        model = RegistroMantencion
        # 🟢 CORRECCIÓN: Dejamos solo los dos campos que sobrevivieron en el modelo
        fields = ['causa_raiz', 'foto_final'] 
        widgets = {
            'causa_raiz': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Origen del problema (para prevención)'}),
        }


class MaterialUtilizadoForm(forms.ModelForm):
    class Meta:
        model = MaterialUtilizado
        fields = ['material', 'cantidad_utilizada', 'observacion']
        
        error_messages = {
            'material': {
                'required': 'Debes seleccionar un artículo válido del pañol.',
            },
            'cantidad_utilizada': {
                'required': 'La cantidad es obligatoria si registras un material.',
                'min_value': 'La cantidad utilizada no puede ser inferior a 1 unidad.',
            }
        }
        
        widgets = {
            'material': forms.Select(attrs={'class': 'form-control'}),
            'cantidad_utilizada': forms.NumberInput(attrs={'step': '1', 'min': '1', 'placeholder': 'Cant.'}),
            'observacion': forms.TextInput(attrs={'placeholder': 'Observación (opcional)'}),
        }


MaterialUtilizadoFormSet = inlineformset_factory(
    SesionTrabajo, MaterialUtilizado,
    form=MaterialUtilizadoForm,
    fields=['material', 'cantidad_utilizada', 'observacion'],
    extra=1, can_delete=True,
)


# ═══════════════════════════════════════════════════════════════
# NO REPARABLE / PAUSA / REACTIVACIÓN
# ═══════════════════════════════════════════════════════════════
class NoReparableForm(forms.ModelForm):
    class Meta:
        model = NoReparable
        fields = ['motivo_tecnico', 'material_requerido', 'criticidad', 'herramientas_faltantes',
                  'personal_especializado_requerido', 'foto_diagnostico', 'requiere_externalizacion']
        widgets = {
            'motivo_tecnico': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Detalle técnico de por qué no se puede reparar'}),
            'material_requerido': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Material específico necesario'}),
            'criticidad': forms.Select(),
            'herramientas_faltantes': forms.Textarea(attrs={'rows': 2, 'placeholder': 'Herramientas faltantes'}),
            'personal_especializado_requerido': forms.TextInput(attrs={'placeholder': 'Especialidad requerida'}),
            'foto_diagnostico': forms.FileInput(attrs={'accept': 'image/*'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['criticidad'].choices = NoReparable.CRITICIDAD_CHOICES


class PausaForm(forms.Form):
    razones_pausa = forms.MultipleChoiceField(
        choices=[],  # poblado dinámicamente desde EstadoCatalogo(entidad='pausa_ticket')
        widget=forms.CheckboxSelectMultiple,
        label='Motivos de pausa (puede seleccionar más de uno)',
    )
    motivo_pausa = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'Detalle y justificación de la pausa'}),
        label='Detalle / Justificación'
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from app.models import EstadoCatalogo
        db = list(EstadoCatalogo.objects.filter(entidad='pausa_ticket', activo=True)
                  .order_by('orden').values_list('codigo', 'nombre_display'))
        self.fields['razones_pausa'].choices = db or Ticket.PAUSA_CHOICES


class ReactivacionForm(forms.Form):
    comentario = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'Razón de la reactivación'}),
        label='Comentario de reactivación'
    )


class DerivarMantencionForm(forms.Form):
    tecnico = forms.ModelChoiceField(
        queryset=Usuario.objects.filter(rol='mantencion', estado_cuenta__codigo='activa'),
        label='Técnico asignado',
        empty_label='Seleccionar técnico...',
    )
    instrucciones = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 2, 'placeholder': 'Instrucciones para el técnico (opcional)'}),
        required=False, label='Instrucciones'
    )


class ReasignarForm(forms.Form):
    nuevo_responsable = forms.ModelChoiceField(
        queryset=Usuario.objects.none(),
        label='Nuevo responsable',
    )
    motivo = forms.CharField(widget=forms.Textarea(attrs={'rows': 2}), label='Motivo de reasignación')

    def __init__(self, *args, **kwargs):
        roles = kwargs.pop('roles', ['guardia', 'mantencion'])
        super().__init__(*args, **kwargs)
        self.fields['nuevo_responsable'].queryset = Usuario.objects.filter(
            rol__in=roles, estado_cuenta__codigo='activa'
        )


# ═══════════════════════════════════════════════════════════════
# INASISTENCIA
# ═══════════════════════════════════════════════════════════════
class InasistenciaForm(forms.ModelForm):
    class Meta:
        model = Inasistencia
        fields = ['fecha_desde', 'fecha_hasta', 'motivo', 'detalle']
        widgets = {
            'fecha_desde': forms.DateInput(attrs={'type': 'date'}),
            'fecha_hasta': forms.DateInput(attrs={'type': 'date'}),
            'detalle': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Información adicional'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from app.models import EstadoCatalogo
        db = list(EstadoCatalogo.objects.filter(entidad='motivo_inasistencia', activo=True)
                  .order_by('orden').values_list('codigo', 'nombre_display'))
        if db:
            self.fields['motivo'].choices = [('', 'Seleccionar motivo…')] + db


# ═══════════════════════════════════════════════════════════════
# MATERIAL (catálogo)
# ═══════════════════════════════════════════════════════════════
class MaterialForm(forms.ModelForm):
    class Meta:
        model = Material
        fields = ['codigo', 'nombre', 'categoria', 'unidad', 'descripcion']


# ═══════════════════════════════════════════════════════════════
# VINCULAR ACTIVO SAP (HU-15)
# ═══════════════════════════════════════════════════════════════
class VincularActivoForm(forms.Form):
    id_activo_sap = forms.CharField(
        label='ID Activo SAP',
        max_length=50,
        required=True,
        widget=forms.TextInput(attrs={'placeholder': 'Código del activo en SAP'})
    )
    descripcion_activo = forms.CharField(
        label='Descripción del Activo',
        max_length=500,
        required=False,
        widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'Descripción del activo vinculado'})
    )


# ═══════════════════════════════════════════════════════════════
# MATERIAL FALTANTE EN MANTENCIÓN
# ═══════════════════════════════════════════════════════════════
class MaterialFaltanteForm(forms.ModelForm):
    class Meta:
        model = MaterialesFaltantes
        fields = ['material', 'cantidad_requerida', 'observaciones']
        widgets = {
            'material': forms.Select(attrs={'class': 'form-control'}),
            'cantidad_requerida': forms.NumberInput(attrs={'step': '0.1', 'min': '0.1', 'placeholder': 'Cantidad necesaria'}),
            'observaciones': forms.Textarea(attrs={'rows': 2, 'placeholder': 'Notas adicionales'}),
        }

class EstimarTicketForm(forms.ModelForm):
    class Meta:
        model = AsignacionTicket
        fields = ['tiempo_estimado', 'diagnostico_preliminar']
        widgets = {
            'tiempo_estimado': forms.NumberInput(attrs={
                'class': 'form-control', 
                'step': '0.5', 
                'min': '0.5', 
                'placeholder': 'Ej: 2.5'
            }),
            'diagnostico_preliminar': forms.Textarea(attrs={
                'class': 'form-control', 
                'rows': 4, 
                'placeholder': 'Escribe un análisis inicial de la falla y qué herramientas podrías necesitar...'
            }),
        }
        labels = {
            'tiempo_estimado': 'Tiempo Estimado de Trabajo (en Horas)',
            'diagnostico_preliminar': 'Diagnóstico Preliminar / Análisis Técnico Inicial',
        }
    
    # 🟢 CORRECCIÓN: Forzamos la validación obligatoria en este formulario específico
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Hacemos que ambos campos sean 100% obligatorios
        self.fields['tiempo_estimado'].required = True
        self.fields['diagnostico_preliminar'].required = True
        
        # Opcional: Le añadimos un asterisco visual a los labels para avisarle al usuario
        self.fields['tiempo_estimado'].label = 'Tiempo Estimado de Trabajo (en Horas) *'
        self.fields['diagnostico_preliminar'].label = 'Diagnóstico Preliminar / Análisis Técnico Inicial *'

    # 🟢 EXTRA: Validación avanzada de reglas de negocio
    def clean_tiempo_estimado(self):
        tiempo = self.cleaned_data.get('tiempo_estimado')
        if tiempo and tiempo <= 0:
            raise ValidationError('El tiempo estimado debe ser mayor a 0 horas.')
        return tiempo