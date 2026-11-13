import re

from django import forms
from django.contrib.auth.password_validation import validate_password
from django.utils.text import slugify

from .models import Categoria, Configuracion, Gasto, Producto, TurnoCaja, Usuario
from .utils import comprimir_imagen

DINERO = {"min_value": 0, "max_digits": 12, "decimal_places": 2}


def input_dinero():
    return forms.NumberInput(attrs={"step": "0.01", "min": "0", "inputmode": "decimal"})


class ProductoForm(forms.ModelForm):
    class Meta:
        model = Producto
        fields = ["nombre", "categoria", "precio", "foto", "activo"]
        widgets = {
            "precio": input_dinero(),
            "foto": forms.ClearableFileInput(attrs={"accept": "image/*"}),
        }
        labels = {"precio": "Precio (Bs)", "activo": "Disponible para la venta"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["categoria"].queryset = Categoria.objects.filter(activo=True)

    def clean_precio(self):
        p = self.cleaned_data["precio"]
        if p <= 0:
            raise forms.ValidationError("El precio debe ser mayor a 0.")
        return p

    def clean_foto(self):
        foto = self.cleaned_data.get("foto")
        # Solo procesar archivos recién subidos
        if foto and hasattr(foto, "content_type"):
            try:
                return comprimir_imagen(foto)
            except Exception:
                raise forms.ValidationError("No se pudo leer la imagen. Use una foto JPG o PNG.")
        return foto


class CategoriaForm(forms.ModelForm):
    class Meta:
        model = Categoria
        fields = ["nombre", "orden", "a_cocina", "activo"]
        labels = {"activo": "Activa"}


class UsuarioForm(forms.ModelForm):
    nombre = forms.CharField(max_length=60)
    pin = forms.CharField(
        label="PIN de 4 dígitos", required=False, max_length=4,
        widget=forms.PasswordInput(attrs={"inputmode": "numeric", "autocomplete": "new-password"}, render_value=False),
    )
    password = forms.CharField(
        label="Contraseña (solo administradores)", required=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )

    class Meta:
        model = Usuario
        fields = ["rol", "is_active"]
        labels = {"is_active": "Activo"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["nombre"].initial = self.instance.first_name
            self.fields["pin"].help_text = "Déjelo vacío para mantener el PIN actual."
            self.fields["password"].help_text = "Déjela vacía para mantener la contraseña actual."
        else:
            self.fields["pin"].required = True

    def clean_pin(self):
        pin = self.cleaned_data.get("pin", "")
        if pin and not re.fullmatch(r"\d{4}", pin):
            raise forms.ValidationError("El PIN debe tener exactamente 4 números.")
        return pin

    def clean(self):
        data = super().clean()
        pwd = data.get("password")
        if data.get("rol") == Usuario.ADMIN:
            necesita = not self.instance.pk or not self.instance.has_usable_password()
            if necesita and not pwd:
                self.add_error("password", "Un administrador necesita contraseña para iniciar sesión.")
        if pwd:
            try:
                validate_password(pwd, self.instance)
            except forms.ValidationError as e:
                self.add_error("password", e)
        return data

    def save(self, commit=True):
        u = super().save(commit=False)
        u.first_name = self.cleaned_data["nombre"].strip()
        if not u.username:
            base = slugify(u.first_name)[:20] or "usuario"
            nombre, i = base, 1
            while Usuario.objects.filter(username=nombre).exists():
                i += 1
                nombre = f"{base}{i}"
            u.username = nombre
        if self.cleaned_data.get("pin"):
            u.set_pin(self.cleaned_data["pin"])
        if self.cleaned_data.get("password"):
            u.set_password(self.cleaned_data["password"])
        elif not u.pk:
            u.set_unusable_password()
        if commit:
            u.save()
        return u


class GastoForm(forms.ModelForm):
    class Meta:
        model = Gasto
        fields = ["fecha", "descripcion", "monto", "turno"]
        widgets = {
            "fecha": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "monto": input_dinero(),
        }
        labels = {"monto": "Monto (Bs)", "turno": "¿Se pagó con el efectivo de una caja abierta?"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["turno"].queryset = TurnoCaja.objects.filter(estado=TurnoCaja.ABIERTA).select_related("usuario")
        self.fields["turno"].empty_label = "No, se pagó por fuera"
        self.fields["turno"].label_from_instance = lambda t: f"Sí, caja de {t.usuario} (#{t.pk})"

    def clean_monto(self):
        m = self.cleaned_data["monto"]
        if m <= 0:
            raise forms.ValidationError("El monto debe ser mayor a 0.")
        return m


class ConfiguracionForm(forms.ModelForm):
    class Meta:
        model = Configuracion
        fields = ["nombre_negocio", "num_mesas", "pie_ticket"]


class AbrirCajaForm(forms.Form):
    monto_inicial = forms.DecimalField(label="Monto inicial en efectivo (Bs)", widget=input_dinero(), **DINERO)


class CerrarCajaForm(forms.Form):
    efectivo_declarado = forms.DecimalField(label="Efectivo contado en caja (Bs)", widget=input_dinero(), **DINERO)
    observacion = forms.CharField(label="Observación (opcional)", required=False,
                                  widget=forms.Textarea(attrs={"rows": 2}))
