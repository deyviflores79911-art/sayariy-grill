from functools import wraps

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from ..models import Usuario

MAX_INTENTOS = 5
BLOQUEO_SEG = 300


def admin_required(view):
    @wraps(view)
    def envoltura(request, *args, **kwargs):
        if not request.user.es_admin:
            messages.error(request, "Solo la administradora puede entrar a esa sección.")
            return redirect("inicio")
        return view(request, *args, **kwargs)

    return login_required(envoltura)


def intentos_bloqueados(clave):
    return cache.get(clave, 0) >= MAX_INTENTOS


def registrar_fallo(clave):
    cache.set(clave, cache.get(clave, 0) + 1, BLOQUEO_SEG)


def verificar_pin_admin(request, pin):
    """Devuelve el administrador dueño del PIN, o None. Con límite de intentos."""
    clave = f"pin_admin_{request.user.pk}"
    if intentos_bloqueados(clave):
        return None
    for adm in Usuario.objects.filter(rol=Usuario.ADMIN, is_active=True):
        if adm.check_pin(pin):
            cache.delete(clave)
            return adm
    registrar_fallo(clave)
    return None


def login_view(request):
    if request.user.is_authenticated:
        return redirect("inicio")
    usuarios = Usuario.objects.filter(is_active=True).order_by("-rol", "first_name")
    error, seleccionado = None, None

    if request.method == "POST":
        u = Usuario.objects.filter(pk=request.POST.get("usuario_id"), is_active=True).first()
        if u is None:
            error = "Seleccione su nombre."
        else:
            seleccionado = u.pk
            clave = f"login_fallo_{u.pk}"
            if intentos_bloqueados(clave):
                error = "Demasiados intentos fallidos. Espere 5 minutos."
            else:
                if u.es_admin:
                    ok = u.check_password(request.POST.get("password", ""))
                else:
                    ok = u.check_pin(request.POST.get("pin", ""))
                if ok:
                    cache.delete(clave)
                    login(request, u)
                    return redirect("inicio")
                registrar_fallo(clave)
                error = "Contraseña incorrecta." if u.es_admin else "PIN incorrecto."

    return render(request, "pos/login.html", {
        "usuarios": usuarios, "error": error, "seleccionado": seleccionado,
    })


@require_POST
def logout_view(request):
    logout(request)
    return redirect("login")


@login_required
def inicio(request):
    if request.user.es_admin:
        return redirect("panel")
    return redirect("venta")
