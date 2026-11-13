from django.contrib import admin

from . import models

for m in (models.Usuario, models.Configuracion, models.Categoria, models.Producto,
          models.TurnoCaja, models.Venta, models.VentaItem, models.Gasto):
    admin.site.register(m)
