from django.core.management.base import BaseCommand
from django.db import transaction

from pos.models import Categoria, Producto


class Command(BaseCommand):
    help = "Deja solo dos categorías: Comida (va a cocina) y Sodas (bebidas). Conserva el orden de los productos."

    @transaction.atomic
    def handle(self, *args, **o):
        # 1) Guardar el orden actual: los productos siguen agrupados como antes
        for p in Producto.objects.select_related("categoria"):
            if p.orden == 0:
                p.orden = p.categoria.orden
                p.save(update_fields=["orden"])
        # 2) Las dos categorías finales
        comida, _ = Categoria.objects.get_or_create(nombre="Comida")
        sodas, _ = Categoria.objects.get_or_create(nombre="Sodas")
        Categoria.objects.filter(pk=comida.pk).update(orden=0, a_cocina=True, activo=True)
        Categoria.objects.filter(pk=sodas.pk).update(orden=1, a_cocina=False, activo=True)
        # 3) Mover productos según si se preparan en cocina
        otras = Categoria.objects.exclude(pk__in=[comida.pk, sodas.pk])
        n_com = Producto.objects.filter(categoria__in=otras.filter(a_cocina=True)).update(categoria=comida)
        n_sod = Producto.objects.filter(categoria__in=otras.filter(a_cocina=False)).update(categoria=sodas)
        # 4) Borrar categorías que quedaron vacías
        borradas = [c.nombre for c in otras if not c.productos.exists()]
        otras.filter(productos__isnull=True).delete()
        self.stdout.write(f"A Comida: {n_com} · A Sodas: {n_sod} · Categorías borradas: {', '.join(borradas) or 'ninguna'}")
        for c in Categoria.objects.all():
            self.stdout.write(f"  {c.nombre}: " + ", ".join(p.nombre for p in c.productos.all()))
