from django.urls import path

from .views import admin, caja, comun, reportes

urlpatterns = [
    path("", comun.inicio, name="inicio"),
    path("ingresar/", comun.login_view, name="login"),
    path("salir/", comun.logout_view, name="logout"),
    # Trabajador
    path("caja/abrir/", caja.caja_abrir, name="caja_abrir"),
    path("caja/cerrar/", caja.caja_cerrar, name="caja_cerrar"),
    path("caja/<int:pk>/", caja.cierre_detalle, name="cierre_detalle"),
    path("vender/", caja.venta, name="venta"),
    path("vender/confirmar/", caja.venta_confirmar, name="venta_confirmar"),
    path("ticket/<int:pk>/", caja.ticket, name="ticket"),
    path("mis-ventas/", caja.mis_ventas, name="mis_ventas"),
    path("venta/<int:pk>/anular/", caja.venta_anular, name="venta_anular"),
    # Administración
    path("admin/", admin.panel, name="panel"),
    path("admin/productos/", admin.productos, name="productos"),
    path("admin/productos/nuevo/", admin.producto_form, name="producto_nuevo"),
    path("admin/productos/<int:pk>/", admin.producto_form, name="producto_editar"),
    path("admin/productos/<int:pk>/activar/", admin.producto_toggle, name="producto_toggle"),
    path("admin/categorias/", admin.categorias, name="categorias"),
    path("admin/categorias/nueva/", admin.categoria_form, name="categoria_nueva"),
    path("admin/categorias/<int:pk>/", admin.categoria_form, name="categoria_editar"),
    path("admin/personal/", admin.trabajadores, name="trabajadores"),
    path("admin/personal/nuevo/", admin.trabajador_form, name="trabajador_nuevo"),
    path("admin/personal/<int:pk>/", admin.trabajador_form, name="trabajador_editar"),
    path("admin/gastos/", admin.gastos, name="gastos"),
    path("admin/gastos/<int:pk>/eliminar/", admin.gasto_eliminar, name="gasto_eliminar"),
    path("admin/ventas/", admin.ventas, name="ventas"),
    path("admin/cierres/", admin.cierres, name="cierres"),
    path("admin/reportes/", reportes.reportes, name="reportes"),
    path("admin/reportes/excel/", reportes.reportes_excel, name="reportes_excel"),
    path("admin/configuracion/", admin.configuracion, name="configuracion"),
]
