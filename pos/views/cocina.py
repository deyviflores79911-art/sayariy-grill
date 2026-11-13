from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from ..models import Venta

VENTANA = timedelta(hours=18)  # pedidos de la jornada


def _pedido(v):
    return {
        "id": v.pk, "numero": v.numero, "hora": v.fecha_hora.isoformat(),
        "destino": v.destino, "cliente": v.cliente, "nota": v.nota, "cajero": v.usuario.nombre,
        "listo_en": v.listo_en.isoformat() if v.listo_en else None,
        "items": [{"cant": i.cantidad, "nombre": i.nombre_producto, "nota": i.nota}
                  for i in v.items.all() if i.a_cocina],
    }


@login_required
def cocina(request):
    return render(request, "pos/cocina.html")


@login_required
def cocina_pedidos(request):
    ahora = timezone.now()
    base = (Venta.objects.filter(estado=Venta.VALIDA, fecha_hora__gte=ahora - VENTANA)
            .select_related("usuario").prefetch_related("items"))
    pendientes = base.filter(cocina_estado=Venta.PENDIENTE).order_by("fecha_hora")
    listos = base.filter(cocina_estado=Venta.LISTO, listo_en__gte=ahora - timedelta(minutes=30),
                         items__a_cocina=True).distinct().order_by("-listo_en")[:12]
    return JsonResponse({
        "ahora": ahora.isoformat(),
        "pendientes": [_pedido(v) for v in pendientes],
        "listos": [_pedido(v) for v in listos],
    })


@login_required
@require_POST
def cocina_listo(request, pk):
    v = get_object_or_404(Venta, pk=pk)
    if v.cocina_estado == Venta.PENDIENTE:
        v.cocina_estado, v.listo_en, v.listo_por = Venta.LISTO, timezone.now(), request.user
        v.save(update_fields=["cocina_estado", "listo_en", "listo_por"])
    return JsonResponse({"ok": True})


@login_required
@require_POST
def cocina_deshacer(request, pk):
    v = get_object_or_404(Venta, pk=pk, estado=Venta.VALIDA)
    v.cocina_estado, v.listo_en, v.listo_por = Venta.PENDIENTE, None, None
    v.save(update_fields=["cocina_estado", "listo_en", "listo_por"])
    return JsonResponse({"ok": True})
