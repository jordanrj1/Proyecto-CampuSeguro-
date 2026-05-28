from django import forms
from django.core.exceptions import ValidationError
from django.forms import inlineformset_factory
from .models import (
    Usuario, Ticket, ValidacionGuardia, RegistroMantencion,
    MaterialUtilizado, Material, NoReparable, Inasistencia, MaterialesFaltantes,
    EstadoCatalogo
)


# ═══════════════════════════════════════════════════════════════
# AUTENTICACIÓN
# ═══════════════════════════════════════════════════════════════
class LoginForm(forms.Form):
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
    password1 = forms.CharField(
        label='Contraseña',
        widget=forms.PasswordInput(attrs={'placeholder': 'Mínimo 8 caracteres'}),
        min_length=8,
    )
    password2 = forms.CharField(
        label='Confirmar Contraseña',
        widget=forms.PasswordInput(attrs={'placeholder': 'Repite la contraseña'}),
    )
    acepta_terminos = forms.BooleanField(
        label='Acepto las políticas de uso institucional',
        required=True,
    )

    class Meta:
        model = Usuario
        fields = [
            'first_name', 'last_name', 'rut', 'correo_institucional',
            'telefono', 'rol',
            'vinculo', 'carrera', 'jornada', 'sede', 'departamento',
            'especialidad', 'turno',
        ]
        widgets = {
            'first_name': forms.TextInput(attrs={'placeholder': 'Juan'}),
            'last_name': forms.TextInput(attrs={'placeholder': 'Pérez González'}),
            'rut': forms.TextInput(attrs={'placeholder': '12.345.678-9'}),
            'correo_institucional': forms.EmailInput(attrs={'placeholder': 'tu.correo@duoc.cl'}),
            'telefono': forms.TextInput(attrs={'placeholder': '+56 9 1234 5678'}),
            'sede': forms.TextInput(attrs={'placeholder': 'Ej: Sede Concepción'}),
            'carrera': forms.TextInput(attrs={'placeholder': 'Ej: Ingeniería en Informática'}),
            'departamento': forms.TextInput(attrs={'placeholder': 'Ej: Operaciones'}),
            'especialidad': forms.TextInput(attrs={'placeholder': 'Ej: Electricidad'}),
            'turno': forms.TextInput(attrs={'placeholder': 'Ej: Mañana / Tarde / Noche'}),
        }

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
        rut = self.cleaned_data['rut'].replace('.', '').replace('-', '').upper()
        if Usuario.objects.filter(rut__iexact=rut).exists():
            raise ValidationError('Este RUT ya está registrado.')
        return rut

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = self.cleaned_data['correo_institucional']
        user.email = self.cleaned_data['correo_institucional']
        user.set_password(self.cleaned_data['password1'])
        user.estado_cuenta = EstadoCatalogo.para('cuenta', 'activa')
        user.is_active = True
        if commit:
            user.save()
        return user


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
    class Meta:
        model = Ticket
        fields = [
            'titulo', 'ubicacion',
            'categoria', 'urgencia', 'descripcion',
            'afecta_clase', 'riesgo_electrico', 'riesgo_estructural', 'riesgo_accesibilidad',
            'foto_evidencia', 'id_activo_sap',
        ]
        widgets = {
            'titulo': forms.TextInput(attrs={'placeholder': 'Ej: Enchufe quemado en sala 305'}),
            'descripcion': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Describe el problema, síntomas y contexto...'}),
            'ubicacion': forms.Select(attrs={'class': 'form-control'}),
            'id_activo_sap': forms.TextInput(attrs={'placeholder': 'ACT-2024-001 (opcional)'}),
        }

    def clean_foto_evidencia(self):
        foto = self.cleaned_data.get('foto_evidencia')
        if not foto and not self.instance.pk:
            raise ValidationError('La foto de evidencia es obligatoria.')
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
        if not cleaned.get('foto_evidencia'):
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
        fields = ['descripcion_trabajo', 'causa_raiz', 'horas_hombre', 'foto_final',
                  'herramientas_utilizadas', 'personal_adicional_requerido', 'requiere_nivel_mayor', 'observaciones']
        widgets = {
            'descripcion_trabajo': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Describe paso a paso lo realizado...'}),
            'causa_raiz': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Origen del problema (para prevención)'}),
            'observaciones': forms.Textarea(attrs={'rows': 2, 'placeholder': 'Notas adicionales'}),
            'horas_hombre': forms.NumberInput(attrs={'step': '0.5', 'min': '0', 'placeholder': '2.5'}),
            'herramientas_utilizadas': forms.Textarea(attrs={'rows': 2, 'placeholder': 'Herramientas usadas'}),
        }


class MaterialUtilizadoForm(forms.ModelForm):
    class Meta:
        model = MaterialUtilizado
        fields = ['material', 'cantidad', 'observacion']
        widgets = {
            'material': forms.Select(attrs={'class': 'form-control'}),
            'cantidad': forms.NumberInput(attrs={'step': '1', 'min': '1', 'placeholder': 'Cant.'}),
            'observacion': forms.TextInput(attrs={'placeholder': 'Observación (opcional)'}),
        }


MaterialUtilizadoFormSet = inlineformset_factory(
    RegistroMantencion, MaterialUtilizado,
    form=MaterialUtilizadoForm,
    fields=['material', 'cantidad', 'observacion'],
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
            'criticidad': forms.Select(choices=NoReparable.CRITICIDAD_CHOICES),
            'herramientas_faltantes': forms.Textarea(attrs={'rows': 2, 'placeholder': 'Herramientas faltantes'}),
            'personal_especializado_requerido': forms.TextInput(attrs={'placeholder': 'Especialidad requerida'}),
            'foto_diagnostico': forms.FileInput(attrs={'accept': 'image/*'}),
        }


class PausaForm(forms.Form):
    razones_pausa = forms.MultipleChoiceField(
        choices=Ticket.PAUSA_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        label='Motivos de pausa (puede seleccionar más de uno)',
    )
    motivo_pausa = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'Detalle y justificación de la pausa'}),
        label='Detalle / Justificación'
    )


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


# ═══════════════════════════════════════════════════════════════
# MATERIAL (catálogo)
# ═══════════════════════════════════════════════════════════════
class MaterialForm(forms.ModelForm):
    class Meta:
        model = Material
        fields = ['codigo', 'nombre', 'categoria', 'unidad', 'stock_actual', 'stock_minimo', 'descripcion']


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
