from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.db.models.functions import ExtractHour, TruncDate
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

from ..models import Gasto, TurnoCaja, Venta, VentaItem
from ..templatetags.pos_tags import formato_bs
from .comun import admin_required

CERO = Decimal("0")
PERIODOS = [("hoy", "Hoy"), ("ayer", "Ayer"), ("semana", "Esta semana"), ("mes", "Este mes"), ("rango", "Rango")]


def obtener_periodo(request):
    """Devuelve (periodo, desde, hasta) como fechas locales, ambas inclusive."""
    hoy = timezone.localdate()
    periodo = request.GET.get("periodo", "hoy")
    if periodo == "ayer":
        return periodo, hoy - timedelta(days=1), hoy - timedelta(days=1)
    if periodo == "semana":
        return periodo, hoy - timedelta(days=hoy.weekday()), hoy
    if periodo == "mes":
        return periodo, hoy.replace(day=1), hoy
    if periodo == "rango":
        try:
            desde = date.fromisoformat(request.GET.get("desde", ""))
            hasta = date.fromisoformat(request.GET.get("hasta", ""))
            if desde > hasta:
                desde, hasta = hasta, desde
            return periodo, desde, hasta
        except ValueError:
            pass
    return "hoy", hoy, hoy


def rango_datetime(desde, hasta):
    tz = timezone.get_current_timezone()
    return (
        timezone.make_aware(datetime.combine(desde, time.min), tz),
        timezone.make_aware(datetime.combine(hasta + timedelta(days=1), time.min), tz),
    )


def con_barras(filas, campo):
    maximo = max((f[campo] or 0 for f in filas), default=0)
    for f in filas:
        f["pct"] = round(float(f[campo] or 0) / float(maximo) * 100) if maximo else 0
    return filas


def datos_reporte(desde, hasta):
    ini, fin = rango_datetime(desde, hasta)
    todas = Venta.objects.filter(fecha_hora__gte=ini, fecha_hora__lt=fin)
    validas = todas.filter(estado=Venta.VALIDA)

    total = validas.aggregate(s=Sum("total"))["s"] or CERO
    num = validas.count()
    anuladas = todas.filter(estado=Venta.ANULADA).aggregate(n=Count("id"), s=Sum("total"))
    gastos = Gasto.objects.filter(fecha__gte=desde, fecha__lte=hasta)
    total_gastos = gastos.aggregate(s=Sum("monto"))["s"] or CERO

    nombres_metodo = dict(Venta.METODOS)
    por_metodo = [
        {"metodo": nombres_metodo[f["metodo_pago"]], "num": f["num"], "total": f["total"]}
        for f in validas.values("metodo_pago").annotate(num=Count("id"), total=Sum("total")).order_by("-total")
    ]
    por_trabajador = [
        {"nombre": f["usuario__first_name"] or f["usuario__username"], "num": f["num"], "total": f["total"]}
        for f in validas.values("usuario__first_name", "usuario__username")
        .annotate(num=Count("id"), total=Sum("total")).order_by("-total")
    ]
    productos = list(
        VentaItem.objects.filter(venta__in=validas).values("nombre_producto")
        .annotate(cantidad=Sum("cantidad"), total=Sum("subtotal")).order_by("-cantidad", "-total")
    )
    por_hora_q = {
        f["hora"]: f for f in validas.annotate(hora=ExtractHour("fecha_hora")).values("hora")
        .annotate(num=Count("id"), total=Sum("total"))
    }
    horas = sorted(por_hora_q)
    por_hora = []
    if horas:
        for h in range(horas[0], horas[-1] + 1):
            f = por_hora_q.get(h, {"num": 0, "total": CERO})
            por_hora.append({"hora": f"{h:02d}:00", "num": f["num"], "total": f["total"]})
    por_dia = [
        {"dia": f["dia"], "num": f["num"], "total": f["total"]}
        for f in validas.annotate(dia=TruncDate("fecha_hora")).values("dia")
        .annotate(num=Count("id"), total=Sum("total")).order_by("dia")
    ]
    cierres = TurnoCaja.objects.filter(
        estado=TurnoCaja.CERRADA, cerrado_en__gte=ini, cerrado_en__lt=fin
    ).select_related("usuario")

    return {
        "desde": desde, "hasta": hasta,
        "total": total, "num": num,
        "ticket_promedio": (total / num) if num else CERO,
        "num_anuladas": anuladas["n"], "total_anuladas": anuladas["s"] or CERO,
        "total_gastos": total_gastos, "ganancia": total - total_gastos,
        "por_metodo": con_barras(por_metodo, "total"),
        "por_trabajador": con_barras(por_trabajador, "total"),
        "productos": con_barras(productos, "cantidad"),
        "por_hora": con_barras(por_hora, "num"),
        "por_dia": con_barras(por_dia, "total"),
        "cierres": cierres,
        "gastos": gastos.select_related("registrado_por"),
        "ventas": todas.select_related("usuario", "anulada_por").prefetch_related("items"),
    }


@admin_required
def reportes(request):
    periodo, desde, hasta = obtener_periodo(request)
    ctx = datos_reporte(desde, hasta)
    ctx.update({"periodo": periodo, "periodos": PERIODOS, "query": request.GET.urlencode()})
    return render(request, "admin_pos/reportes.html", ctx)


@admin_required
def reportes_excel(request):
    periodo, desde, hasta = obtener_periodo(request)
    d = datos_reporte(desde, hasta)
    wb = Workbook()
    negrita = Font(bold=True, color="FFFFFF")
    relleno = PatternFill("solid", fgColor="B71C1C")
    MONEDA = '#,##0.00'

    def hoja(titulo, encabezados, filas, moneda=(), primera=False):
        ws = wb.active if primera else wb.create_sheet()
        ws.title = titulo
        ws.append(encabezados)
        for c in ws[1]:
            c.font, c.fill = negrita, relleno
        for f in filas:
            ws.append(list(f))
        for col in moneda:
            for celda in ws.iter_cols(min_col=col, max_col=col, min_row=2):
                for c in celda:
                    c.number_format = MONEDA
        for i, _ in enumerate(encabezados, 1):
            letra = ws.cell(row=1, column=i).column_letter
            ancho = max(len(str(c.value or "")) for c in ws[letra])
            ws.column_dimensions[letra].width = min(max(ancho + 2, 10), 50)
        return ws

    hoja("Resumen", ["Concepto", "Valor"], [
        ("Desde", desde.strftime("%d/%m/%Y")), ("Hasta", hasta.strftime("%d/%m/%Y")),
        ("Ventas válidas (Bs)", d["total"]), ("Número de ventas", d["num"]),
        ("Ticket promedio (Bs)", d["ticket_promedio"]),
        ("Ventas anuladas", d["num_anuladas"]), ("Monto anulado (Bs)", d["total_anuladas"]),
        ("Gastos (Bs)", d["total_gastos"]), ("Ganancia simple (Bs)", d["ganancia"]),
    ], primera=True)
    loc = timezone.localtime
    hoja("Ventas", ["N°", "Fecha", "Hora", "Trabajador", "Destino", "Cliente", "Nota", "Método", "Total",
                    "Estado", "Motivo anulación", "Anulada por"], [
        (v.numero, loc(v.fecha_hora).strftime("%d/%m/%Y"), loc(v.fecha_hora).strftime("%H:%M"),
         v.usuario.nombre, v.destino, v.cliente, v.nota, v.get_metodo_pago_display(), v.total,
         v.get_estado_display(), v.motivo_anulacion, v.anulada_por.nombre if v.anulada_por else "")
        for v in d["ventas"]
    ], moneda=(9,))
    hoja("Detalle", ["N° venta", "Fecha", "Producto", "Cantidad", "Precio", "Subtotal", "Nota", "Estado"], [
        (v.numero, loc(v.fecha_hora).strftime("%d/%m/%Y %H:%M"), i.nombre_producto, i.cantidad,
         i.precio_unitario, i.subtotal, i.nota, v.get_estado_display())
        for v in d["ventas"] for i in v.items.all()
    ], moneda=(5, 6))
    hoja("Productos", ["Producto", "Cantidad", "Total"],
         [(p["nombre_producto"], p["cantidad"], p["total"]) for p in d["productos"]], moneda=(3,))
    hoja("Trabajadores", ["Trabajador", "Ventas", "Total"],
         [(t["nombre"], t["num"], t["total"]) for t in d["por_trabajador"]], moneda=(3,))
    hoja("Métodos de pago", ["Método", "Ventas", "Total"],
         [(m["metodo"], m["num"], m["total"]) for m in d["por_metodo"]], moneda=(3,))
    hoja("Por hora", ["Hora", "Ventas", "Total"],
         [(h["hora"], h["num"], h["total"]) for h in d["por_hora"]], moneda=(3,))
    hoja("Por día", ["Día", "Ventas", "Total"],
         [(x["dia"].strftime("%d/%m/%Y"), x["num"], x["total"]) for x in d["por_dia"]], moneda=(3,))
    hoja("Cierres de caja", ["Caja", "Trabajador", "Apertura", "Cierre", "Inicial", "Efectivo", "QR",
                             "Tarjeta", "Gastos", "Esperado", "Declarado", "Diferencia", "Observación"], [
        (t.pk, t.usuario.nombre, loc(t.abierto_en).strftime("%d/%m/%Y %H:%M"),
         loc(t.cerrado_en).strftime("%d/%m/%Y %H:%M"), t.monto_inicial, t.ventas_efectivo, t.ventas_qr,
         t.ventas_tarjeta, t.gastos_caja, t.efectivo_esperado, t.efectivo_declarado, t.diferencia, t.observacion)
        for t in d["cierres"]
    ], moneda=range(5, 13))
    hoja("Gastos", ["Fecha", "Descripción", "Monto", "De caja", "Registrado por"], [
        (g.fecha.strftime("%d/%m/%Y"), g.descripcion, g.monto, f"Caja #{g.turno_id}" if g.turno_id else "No",
         g.registrado_por.nombre) for g in d["gastos"]
    ], moneda=(3,))

    resp = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    nombre = f"reporte_{desde:%Y-%m-%d}_a_{hasta:%Y-%m-%d}.xlsx"
    resp["Content-Disposition"] = f'attachment; filename="{nombre}"'
    wb.save(resp)
    return resp
