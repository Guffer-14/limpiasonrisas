from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import ConsultaContacto, Clinica, Producto, REGION_CHOICES

WIDGET_CLASS = {'class': 'form-control ls-input'}
SELECT_CLASS = {'class': 'form-select ls-input'}

DIAS_CHOICES = [
    ('lunes_viernes', 'Lunes a Viernes'),
    ('lunes_sabado',  'Lunes a Sábado'),
    ('manana',        'Solo mañanas (9:00–13:00)'),
    ('tarde',         'Solo tardes (14:00–18:00)'),
    ('cualquier_dia', 'Cualquier día/horario'),
]


class LoginForm(forms.Form):
    username = forms.CharField(
        label='Usuario',
        widget=forms.TextInput(attrs={**WIDGET_CLASS, 'placeholder': 'Tu nombre de usuario', 'autofocus': True})
    )
    password = forms.CharField(
        label='Contraseña',
        widget=forms.PasswordInput(attrs={**WIDGET_CLASS, 'placeholder': '••••••••'})
    )


class RegistroForm(UserCreationForm):
    first_name = forms.CharField(label='Nombre',
        widget=forms.TextInput(attrs={**WIDGET_CLASS, 'placeholder': 'Tu nombre'}))
    last_name = forms.CharField(label='Apellido',
        widget=forms.TextInput(attrs={**WIDGET_CLASS, 'placeholder': 'Tu apellido'}))
    email = forms.EmailField(label='Email',
        widget=forms.EmailInput(attrs={**WIDGET_CLASS, 'placeholder': 'correo@ejemplo.com'}))

    class Meta:
        model  = User
        fields = ('username', 'first_name', 'last_name', 'email', 'password1', 'password2')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for fname, ph in [('username','Nombre de usuario'),('password1','Contraseña'),('password2','Repite la contraseña')]:
            self.fields[fname].widget.attrs.update({**WIDGET_CLASS, 'placeholder': ph})


class ContactoAvanzadoForm(forms.ModelForm):
    dias_respuesta = forms.MultipleChoiceField(
        choices=[
            ('lunes',        'Lunes'),
            ('martes',       'Martes'),
            ('miercoles',    'Miércoles'),
            ('jueves',       'Jueves'),
            ('viernes',      'Viernes'),
            ('sabado',       'Sábado'),
            ('domingo',      'Domingo'),
            ('cualquier_dia','Cualquier día'),
        ],
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label='Días disponibles para respuesta',
    )

    class Meta:
        model  = ConsultaContacto
        fields = ['nombre', 'email', 'telefono', 'direccion',
                  'es_clinica', 'region', 'tipo_consulta',
                  'canal_respuesta', 'dias_respuesta', 'horario_respuesta',
                  'mensaje', 'adjunto']
        widgets = {
            'nombre':           forms.TextInput(attrs={**WIDGET_CLASS,
                                'placeholder': 'Tu nombre completo'}),
            'email':            forms.EmailInput(attrs={**WIDGET_CLASS,
                                'placeholder': 'correo@ejemplo.com'}),
            'telefono':         forms.TextInput(attrs={**WIDGET_CLASS,
                                'placeholder': '9XXXXXXXX', 'maxlength': '9',
                                'pattern': '9[0-9]{8}',
                                'title': 'Ingresa 9 dígitos comenzando con 9'}),
            'direccion':        forms.TextInput(attrs={**WIDGET_CLASS,
                                'placeholder': 'Calle, número, ciudad',
                                'id': 'id_direccion_autocomplete'}),
            'es_clinica':       forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'region':           forms.Select(attrs=SELECT_CLASS),
            'tipo_consulta':    forms.Select(attrs=SELECT_CLASS),
            'canal_respuesta':  forms.Select(attrs=SELECT_CLASS),
            'horario_respuesta': forms.Select(attrs=SELECT_CLASS),
            'mensaje':          forms.Textarea(attrs={**WIDGET_CLASS, 'rows': 5,
                                'placeholder': 'Cuéntanos en qué podemos ayudarte…'}),
            'adjunto':          forms.FileInput(attrs={'class': 'form-control'}),
        }
        labels = {
            'canal_respuesta':   '¿Por qué canal prefieres que te respondamos?',
            'horario_respuesta': 'Horario preferido de respuesta',
            'direccion':         'Dirección',
            'es_clinica':        'Soy Clínica Dental',
        }

    def clean_telefono(self):
        tel = self.cleaned_data.get('telefono', '').strip().replace(' ', '')
        if not tel:
            raise forms.ValidationError('El teléfono es obligatorio.')
        if not tel.isdigit():
            raise forms.ValidationError('Solo se permiten números.')
        if not tel.startswith('9'):
            raise forms.ValidationError('El teléfono debe comenzar con 9.')
        if len(tel) != 9:
            raise forms.ValidationError('El teléfono debe tener 9 dígitos.')
        return tel


class ProductoSoloNombreMarcaField(forms.ModelMultipleChoiceField):
    def label_from_instance(self, obj):
        return f"{obj.nombre} – {obj.marca}" if obj.marca else obj.nombre


class ClinicaForm(forms.ModelForm):
    productos_interes = ProductoSoloNombreMarcaField(
        queryset=Producto.objects.filter(activo=True),
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'ls-checkbox'}),
        required=False,
        label='Productos de interés',
    )

    def label_from_instance_producto(self, obj):
        return f"{obj.nombre} – {obj.marca}" if obj.marca else obj.nombre
    dias_contacto = forms.ChoiceField(
        choices=DIAS_CHOICES,
        widget=forms.Select(attrs=SELECT_CLASS),
        label='¿Cuándo podemos contactarte?',
        required=False,
    )

    class Meta:
        model  = Clinica
        fields = ['nombre_clinica', 'rut', 'direccion', 'ciudad', 'region',
                  'telefono', 'email', 'sitio_web',
                  'nombre_contacto', 'cargo_contacto',
                  'medio_contacto', 'dias_contacto',
                  'productos_interes', 'producto_no_catalogo',
                  'rotacion_estimada']
        widgets = {
            'nombre_clinica':       forms.TextInput(attrs={**WIDGET_CLASS, 'placeholder': 'Nombre de la clínica'}),
            'rut':                  forms.TextInput(attrs={**WIDGET_CLASS, 'placeholder': '76543210-9'}),
            'direccion':            forms.TextInput(attrs={**WIDGET_CLASS, 'placeholder': 'Calle, número'}),
            'ciudad':               forms.TextInput(attrs={**WIDGET_CLASS, 'placeholder': 'Ciudad'}),
            'region':               forms.Select(attrs=SELECT_CLASS),
            'telefono':             forms.TextInput(attrs={**WIDGET_CLASS, 'placeholder': '+56 9 XXXX XXXX'}),
            'email':                forms.EmailInput(attrs={**WIDGET_CLASS, 'placeholder': 'clinica@ejemplo.com'}),
            'sitio_web':            forms.URLInput(attrs={**WIDGET_CLASS, 'placeholder': 'https://'}),
            'nombre_contacto':      forms.TextInput(attrs={**WIDGET_CLASS, 'placeholder': 'Dr./Dra. Apellido'}),
            'cargo_contacto':       forms.TextInput(attrs={**WIDGET_CLASS, 'placeholder': 'Director/a, Administrador/a…'}),
            'medio_contacto':       forms.Select(attrs=SELECT_CLASS),
            'producto_no_catalogo': forms.Textarea(attrs={**WIDGET_CLASS, 'rows': 3,
                                                          'placeholder': 'Ej: Pasta Colgate Sensitive Pro-Alivio 90g, Hilo dental Oral-B…'}),
            'rotacion_estimada':    forms.Select(attrs=SELECT_CLASS),
        }
        labels = {
            'medio_contacto':       '¿Cómo prefieres que te contactemos?',
            'producto_no_catalogo': '¿Buscas algún producto que no está en nuestro catálogo?',
        }
