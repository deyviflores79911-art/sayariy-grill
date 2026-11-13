import hashlib
from functools import wraps

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from ..models import Dispositivo, Usuario

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


def vendedor_required(view):
    """Caja y ventas: administradora y cajeros. La cocina va a su pantalla."""
    @wraps(view)
    def envoltura(request, *args, **kwargs):
        if request.user.es_cocina:
            return redirect("cocina")
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
    if request.user.es_cocina:
        return redirect("cocina")
    return redirect("venta")


def _ip(request):
    ip = request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip() or request.META.get("REMOTE_ADDR", "")
    return ip.rsplit(":", 1)[0] if ip.count(":") == 1 else ip  # Azure agrega ":puerto"


def equipo_view(request):
    """Pantalla para equipos no autorizados: la administradora entra o autoriza el equipo."""
    if not settings.REQUIERE_DISPOSITIVO or getattr(request, "dispositivo", None):
        return redirect("login")
    error = None
    if request.method == "POST":
        usuario = request.POST.get("usuario", "").strip()
        claves = [f"equipo_ip_{_ip(request)}"[:200],
                  "equipo_usr_" + hashlib.sha256(usuario.lower().encode()).hexdigest()]
        if any(intentos_bloqueados(c) for c in claves):
            error = "Demasiados intentos fallidos. Espere 5 minutos."
        else:
            u = authenticate(request, username=usuario, password=request.POST.get("password", ""))
            if u and u.es_admin:
                for c in claves:
                    cache.delete(c)
                login(request, u)
                resp = redirect("inicio")
                if request.POST.get("autorizar"):
                    nombre = request.POST.get("nombre", "").strip()[:60] or "Equipo sin nombre"
                    _, token = Dispositivo.crear(nombre, u)
                    resp.set_cookie(Dispositivo.COOKIE, token, max_age=60 * 60 * 24 * 365 * 5,
                                    httponly=True, secure=request.is_secure(), samesite="Lax")
                    messages.success(request, f"Equipo «{nombre}» autorizado. El personal ya puede entrar aquí con su PIN.")
                return resp
            for c in claves:
                registrar_fallo(c)
            error = "Usuario o contraseña incorrectos (solo la administradora puede autorizar equipos)."
    return render(request, "pos/equipo.html", {"error": error})
