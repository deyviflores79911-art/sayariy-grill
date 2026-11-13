from decimal import Decimal

from django.core.management.base import BaseCommand

from pos.models import Categoria, Producto, Usuario

DATOS = {
    "Platos": [("Pique macho", "55"), ("Silpancho", "35"), ("Chicharrón", "45"), ("Lomo montado", "40"),
               ("Parrillada para 2", "120"), ("Pollo a la parrilla", "38")],
    "Bebidas": [("Coca Cola 2L", "18"), ("Coca Cola personal", "6"), ("Agua sin gas", "5"), ("Cerveza Paceña", "15")],
    "Refrescos": [("Mocochinchi", "5"), ("Limonada", "6"), ("Jugo de linaza", "5"), ("Somó", "6")],
    "Postres": [("Helado de canela", "8"), ("Flan", "7")],
}


class Command(BaseCommand):
    help = "Carga categorías, productos y un trabajador de ejemplo (PIN 1234)."

    def handle(self, *args, **o):
        for orden, (cat, productos) in enumerate(DATOS.items()):
            c, _ = Categoria.objects.get_or_create(nombre=cat, defaults={"orden": orden})
            for nombre, precio in productos:
                Producto.objects.get_or_create(nombre=nombre, defaults={"categoria": c, "precio": Decimal(precio)})
        if not Usuario.objects.filter(username="juan").exists():
            u = Usuario(username="juan", first_name="Juan", rol=Usuario.TRABAJADOR)
            u.set_unusable_password()
            u.set_pin("1234")
            u.save()
        self.stdout.write(self.style.SUCCESS("Datos de ejemplo cargados. Trabajador: Juan, PIN 1234."))
