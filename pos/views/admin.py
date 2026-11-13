from django.conf import settings
from django.contrib import messages
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from ..forms import CategoriaForm, ConfiguracionForm, GastoForm, ProductoForm, UsuarioForm
from ..models import Categoria, Configuracion, Dispositivo, Gasto, Producto, TurnoCaja, Usuario, Venta
from .comun import admin_required
from .reportes import PERIODOS, datos_reporte, obtener_periodo, rango_datetime


@admin_required
def panel(request):
    hoy = timezone.localdate()
    d = datos_reporte(hoy, hoy)
    abiertas = [(t, t.calcular()) for t in TurnoCaja.objects.filter(estado=TurnoCaja.ABIERTA).select_related("usuario")]
    return render(request, "admin_pos/panel.html", {
        "d": d, "abiertas": abiertas,
        "ultimas": d["ventas"][:8],
        "mi_turno": request.user.turno_abierto(),
    })


def _formulario(request, form_class, instancia, plantilla, titulo, volver, archivos=False):
    form = form_class(request.POST or None, (request.FILES or None) if archivos else None, instance=instancia)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Guardado correctamente.")
        return redirect(volver)
    return render(request, plantilla, {"form": form, "titulo": titulo, "volver": volver, "obj": instancia})


# ---------- Productos ----------
@admin_required
def productos(request):
    qs = Producto.objects.select_related("categoria")
    cat = request.GET.get("cat")
    if cat:
        qs = qs.filter(categoria_id=cat)
    return render(request, "admin_pos/productos.html", {
        "productos": qs, "categorias": Categoria.objects.all(), "cat": cat,
    })


@admin_required
def producto_form(request, pk=None):
    obj = get_object_or_404(Producto, pk=pk) if pk else None
    if not Categoria.objects.filter(activo=True).exists():
        messages.info(request, "Primero cree al menos una categoría.")
        return redirect("categoria_nueva")
    return _formulario(request, ProductoForm, obj, "admin_pos/form.html",
                       "Editar producto" if obj else "Nuevo producto", "productos", archivos=True)


@admin_required
@require_POST
def producto_toggle(request, pk):
    p = get_object_or_404(Producto, pk=pk)
    p.activo = not p.activo
    p.save(update_fields=["activo", "actualizado_en"])
    messages.success(request, f"{p.nombre}: {'activado' if p.activo else 'desactivado'}.")
    return redirect(request.POST.get("volver") or "productos")


# ---------- Categorías ----------
@admin_required
def categorias(request):
    return render(request, "admin_pos/categorias.html", {
        "categorias": Categoria.objects.annotate(n=Count("productos")),
    })


@admin_required
def categoria_form(request, pk=None):
    obj = get_object_or_404(Categoria, pk=pk) if pk else None
    return _formulario(request, CategoriaForm, obj, "admin_pos/form.html",
                       "Editar categoría" if obj else "Nueva categoría", "categorias")


# ---------- Trabajadores ----------
@admin_required
def trabajadores(request):
    return render(request, "admin_pos/trabajadores.html", {
        "usuarios": Usuario.objects.order_by("-is_active", "rol", "first_name"),
    })


@admin_required
def trabajador_form(request, pk=None):
    obj = get_object_or_404(Usuario, pk=pk) if pk else Usuario()
    form = UsuarioForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        if obj.pk == request.user.pk and (
            not form.cleaned_data["is_active"] or form.cleaned_data["rol"] != Usuario.ADMIN
        ):
            messages.error(request, "No puede quitarse a sí misma el rol de administradora ni desactivarse.")
        else:
            form.save()
            messages.success(request, "Guardado correctamente.")
            return redirect("trabajadores")
    return render(request, "admin_pos/form.html", {
        "form": form, "titulo": "Editar persona" if obj.pk else "Nueva persona", "volver": "trabajadores",
        "nota": "Los trabajadores entran con su PIN. La administradora entra con contraseña y usa su PIN "
                "para autorizar anulaciones.",
    })


# ---------- Gastos ----------
@admin_required
def gastos(request):
    periodo, desde, hasta = obtener_periodo(request)
    form = GastoForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        g = form.save(commit=False)
        g.registrado_por = request.user
        g.save()
        messages.success(request, "Gasto registrado.")
        return redirect(request.get_full_path())
    lista = Gasto.objects.filter(fecha__gte=desde, fecha__lte=hasta).select_related("registrado_por", "turno__usuario")
    return render(request, "admin_pos/gastos.html", {
        "form": form, "gastos": lista, "total": lista.aggregate(s=Sum("monto"))["s"] or 0,
        "periodo": periodo, "periodos": PERIODOS, "desde": desde, "hasta": hasta,
    })


@admin_required
@require_POST
def gasto_eliminar(request, pk):
    g = get_object_or_404(Gasto, pk=pk)
    if g.turno and g.turno.estado == TurnoCaja.CERRADA:
        messages.error(request, "No se puede eliminar: ese gasto pertenece a una caja ya cerrada.")
    else:
        g.delete()
        messages.success(request, "Gasto eliminado.")
    return redirect(request.POST.get("volver") or "gastos")


# ---------- Ventas y anulaciones ----------
@admin_required
def ventas(request):
    periodo, desde, hasta = obtener_periodo(request)
    ini, fin = rango_datetime(desde, hasta)
    qs = Venta.objects.filter(fecha_hora__gte=ini, fecha_hora__lt=fin).select_related(
        "usuario", "anulada_por", "autorizada_por").prefetch_related("items")
    estado = request.GET.get("estado", "")
    if estado in (Venta.VALIDA, Venta.ANULADA):
        qs = qs.filter(estado=estado)
    trabajador = request.GET.get("trabajador", "")
    if trabajador:
        qs = qs.filter(usuario_id=trabajador)
    return render(request, "admin_pos/ventas.html", {
        "ventas": qs, "periodo": periodo, "periodos": PERIODOS, "desde": desde, "hasta": hasta,
        "estado": estado, "trabajador": trabajador, "usuarios": Usuario.objects.order_by("first_name"),
        "total": qs.filter(estado=Venta.VALIDA).aggregate(s=Sum("total"))["s"] or 0,
    })


# ---------- Cierres ----------
@admin_required
def cierres(request):
    periodo, desde, hasta = obtener_periodo(request)
    ini, fin = rango_datetime(desde, hasta)
    qs = TurnoCaja.objects.filter(
        Q(estado=TurnoCaja.ABIERTA) | Q(cerrado_en__gte=ini, cerrado_en__lt=fin)
    ).select_related("usuario").order_by("estado", "-cerrado_en")
    return render(request, "admin_pos/cierres.html", {
        "turnos": qs, "periodo": periodo, "periodos": PERIODOS, "desde": desde, "hasta": hasta,
    })


# ---------- Configuración ----------
@admin_required
def configuracion(request):
    return _formulario(request, ConfiguracionForm, Configuracion.get(), "admin_pos/form.html",
                       "Configuración", "configuracion")


# ---------- Equipos autorizados ----------
@admin_required
def equipos(request):
    return render(request, "admin_pos/equipos.html", {
        "equipos": Dispositivo.objects.select_related("creado_por"),
        "actual": getattr(request, "dispositivo", None),
        "requiere": settings.REQUIERE_DISPOSITIVO,
    })


@admin_required
@require_POST
def equipo_revocar(request, pk):
    d = get_object_or_404(Dispositivo, pk=pk)
    d.activo = False
    d.save(update_fields=["activo"])
    messages.success(request, f"Se quitó la autorización a «{d.nombre}».")
    return redirect("equipos")
