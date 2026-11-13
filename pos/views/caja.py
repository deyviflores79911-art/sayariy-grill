import json
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from ..forms import AbrirCajaForm, CerrarCajaForm
from ..models import Categoria, Configuracion, Producto, TurnoCaja, Venta, VentaItem
from .comun import verificar_pin_admin


@login_required
def caja_abrir(request):
    if request.user.turno_abierto():
        return redirect("venta")
    form = AbrirCajaForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            TurnoCaja.objects.create(usuario=request.user, monto_inicial=form.cleaned_data["monto_inicial"])
        except IntegrityError:
            pass  # doble clic: ya existe una caja abierta
        messages.success(request, "Caja abierta. ¡Buen turno!")
        return redirect("venta")
    return render(request, "pos/caja_abrir.html", {"form": form})


@login_required
def caja_cerrar(request):
    turno = request.user.turno_abierto()
    if not turno:
        messages.info(request, "No tiene una caja abierta.")
        return redirect("inicio")
    form = CerrarCajaForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        turno.cerrar(form.cleaned_data["efectivo_declarado"], form.cleaned_data["observacion"])
        return redirect("cierre_detalle", pk=turno.pk)
    return render(request, "pos/caja_cerrar.html", {"turno": turno, "c": turno.calcular(), "form": form})


@login_required
def cierre_detalle(request, pk):
    turno = get_object_or_404(TurnoCaja.objects.select_related("usuario"), pk=pk)
    if not request.user.es_admin and turno.usuario_id != request.user.pk:
        raise Http404
    return render(request, "pos/cierre_detalle.html", {
        "turno": turno,
        "c": turno.calcular() if turno.estado == TurnoCaja.ABIERTA else None,
        "gastos": turno.gastos.all(),
    })


@login_required
def venta(request):
    turno = request.user.turno_abierto()
    if not turno:
        messages.info(request, "Primero abra la caja para poder vender.")
        return redirect("caja_abrir")
    categorias = Categoria.objects.filter(activo=True, productos__activo=True).distinct()
    productos = [
        {
            "id": p.pk, "nombre": p.nombre, "precio": str(p.precio), "cat": p.categoria_id,
            "foto": p.foto.url if p.foto else "",
        }
        for p in Producto.objects.filter(activo=True, categoria__activo=True)
    ]
    return render(request, "pos/venta.html", {
        "categorias": categorias, "productos": productos,
        "num_mesas": Configuracion.get().num_mesas,
    })


def _error(msg, status=400):
    return JsonResponse({"ok": False, "error": msg}, status=status)


@login_required
@require_POST
def venta_confirmar(request):
    turno = request.user.turno_abierto()
    if not turno:
        return _error("No tiene una caja abierta.")
    try:
        data = json.loads(request.body)
        items = data.get("items") or []
        if not items:
            return _error("El pedido está vacío.")
        ids = [int(i["id"]) for i in items]
        productos = Producto.objects.in_bulk(ids)
        lineas, total = [], Decimal("0")
        for it in items:
            p = productos.get(int(it["id"]))
            if not p or not p.activo:
                return _error("Uno de los productos ya no está disponible. Recargue la pantalla.")
            cant = int(it["cantidad"])
            if not 1 <= cant <= 999:
                return _error("Cantidad no válida.")
            sub = p.precio * cant
            total += sub
            lineas.append((p, cant, sub, str(it.get("nota", "")).strip()[:200]))

        metodo = data.get("metodo")
        if metodo not in dict(Venta.METODOS):
            return _error("Elija el método de pago.")
        tipo = data.get("tipo")
        mesa = None
        if tipo == Venta.MESA:
            mesa = int(data.get("mesa") or 0)
            if not 1 <= mesa <= Configuracion.get().num_mesas:
                return _error("Elija el número de mesa.")
        elif tipo != Venta.LLEVAR:
            return _error("Elija mesa o para llevar.")

        recibido = cambio = None
        if metodo == Venta.EFECTIVO:
            recibido = Decimal(str(data.get("recibido"))).quantize(Decimal("0.01"))
            if recibido < total:
                return _error("El monto recibido es menor al total.")
            cambio = recibido - total
    except (ValueError, KeyError, TypeError, InvalidOperation, json.JSONDecodeError):
        return _error("Datos del pedido no válidos.")

    with transaction.atomic():
        v = Venta.objects.create(
            turno=turno, usuario=request.user, tipo=tipo, mesa=mesa, metodo_pago=metodo,
            total=total, monto_recibido=recibido, cambio=cambio,
        )
        VentaItem.objects.bulk_create([
            VentaItem(venta=v, producto=p, nombre_producto=p.nombre, precio_unitario=p.precio,
                      cantidad=cant, subtotal=sub, nota=nota)
            for p, cant, sub, nota in lineas
        ])
    return JsonResponse({"ok": True, "url": reverse("ticket", args=[v.pk])})


@login_required
def ticket(request, pk):
    v = get_object_or_404(Venta.objects.select_related("usuario"), pk=pk)
    if not request.user.es_admin and v.usuario_id != request.user.pk:
        raise Http404
    return render(request, "pos/ticket.html", {"v": v, "items": v.items.all()})


@login_required
def mis_ventas(request):
    turno = request.user.turno_abierto()
    ventas = turno.ventas.prefetch_related("items") if turno else Venta.objects.none()
    return render(request, "pos/mis_ventas.html", {
        "turno": turno, "ventas": ventas, "c": turno.calcular() if turno else None,
    })


@login_required
@require_POST
def venta_anular(request, pk):
    v = get_object_or_404(Venta, pk=pk)
    volver = request.POST.get("volver") or reverse("inicio")
    if not volver.startswith("/"):
        volver = reverse("inicio")
    motivo = request.POST.get("motivo", "").strip()

    if v.anulada:
        messages.info(request, "Esa venta ya estaba anulada.")
        return redirect(volver)
    if len(motivo) < 3:
        messages.error(request, "Debe escribir el motivo de la anulación.")
        return redirect(volver)

    if request.user.es_admin:
        autoriza = request.user
    else:
        turno = request.user.turno_abierto()
        if not turno or v.turno_id != turno.pk:
            messages.error(request, "Solo puede anular ventas de su caja abierta.")
            return redirect(volver)
        autoriza = verificar_pin_admin(request, request.POST.get("pin_admin", ""))
        if not autoriza:
            messages.error(request, "PIN de administradora incorrecto. La venta NO fue anulada.")
            return redirect(volver)

    v.anular(motivo, por=request.user, autorizada_por=autoriza)
    messages.success(request, f"Venta {v.numero} anulada.")
    return redirect(volver)
