from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from pos.models import Categoria, Configuracion, Producto, VentaItem
from pos.utils import comprimir_imagen

FOTOS = Path(settings.BASE_DIR) / "menu_fotos"

# (categoría, [(nombre, precio, foto)])  – precio None = falta definir (queda inactivo)
MENU = [
    ("Pollo al cilindro", [
        ("Económico pierna y contra", "18", "pollo"),
        ("Económico pecho", "20", "pollo"),
        ("Económico ala", "20", "pollo"),
        ("Cuarto pierna", "28", "pollo"),
        ("Cuarto pecho", "30", "pollo"),
    ]),
    ("Costillitas", [
        ("Costillitas porción chica", "20", "costillas"),
        ("Costillitas porción grande", "25", "costillas"),
    ]),
    ("Hamburguesas", [
        ("Hamburguesa a la parrilla", "25", "hamburguesa"),
        ("Hamburguesa + papitas", "28", "hamburguesa"),
    ]),
    ("Chicharrón", [("Chicharrón de pollo", "20", "chicharron")]),
    ("Chuleta", [("Chuleta asada", "20", "chuleta")]),
    ("Tallarín salteado", [
        ("Tallarín de carne", "25", "tallarin"),
        ("Tallarín de pollo", "20", "tallarin"),
    ]),
    ("Refrescos", [
        ("Limonada", "3", "limonada"),
        ("Lima", "3", "limonada"),
        ("Maracuyá", "3", "maracuya"),
    ]),
    ("Sodas", [  # la marca se elige con los botones rápidos de la nota
        ("Soda pequeña", "5", "soda"),
        ("Soda personal", "7", "soda"),
        ("Soda 1 litro", "10", "soda"),
        ("Soda 2 litros", "18", "soda"),
    ]),
    ("Cervezas", [("Cerveza Paceña", "20", None)]),
]


class Command(BaseCommand):
    help = "Reemplaza el catálogo con el menú real de Sayariy Grill."

    def handle(self, *args, **o):
        if VentaItem.objects.exists():
            raise CommandError("Ya hay ventas registradas: edite los productos desde la pantalla Productos.")
        Producto.objects.all().delete()
        Categoria.objects.all().delete()

        for orden, (cat, productos) in enumerate(MENU):
            c = Categoria.objects.create(nombre=cat, orden=orden,
                                         a_cocina=cat not in ("Refrescos", "Sodas", "Cervezas"))
            for nombre, precio, foto in productos:
                p = Producto(nombre=nombre, categoria=c,
                             precio=Decimal(precio or "0"), activo=precio is not None)
                ruta = FOTOS / f"{foto}.jpg" if foto else None
                if ruta and ruta.exists():
                    with open(ruta, "rb") as f:
                        img = comprimir_imagen(f)
                    p.foto.save(f"{foto}.jpg", img, save=False)
                p.save()

        cfg = Configuracion.get()
        cfg.nombre_negocio = "Sayariy Grill"
        cfg.pie_ticket = "El origen del verdadero sabor · Pedidos: 63980601 – 71066832"
        cfg.save()
        self.stdout.write(self.style.SUCCESS(
            f"Menú cargado: {Producto.objects.filter(activo=True).count()} productos activos, "
            f"{Producto.objects.filter(activo=False).count()} inactivos."))
