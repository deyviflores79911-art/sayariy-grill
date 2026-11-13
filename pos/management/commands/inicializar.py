import os

from django.core.management import call_command
from django.core.management.base import BaseCommand

from pos.models import Categoria, Usuario


class Command(BaseCommand):
    help = "Primer arranque en el servidor: crea la administradora y carga el menú si no existen."

    def handle(self, *args, **o):
        if not Usuario.objects.filter(rol=Usuario.ADMIN).exists():
            pwd, pin = os.environ.get("ADMIN_PASSWORD"), os.environ.get("ADMIN_PIN")
            if pwd and pin:
                call_command("crear_admin", nombre=os.environ.get("ADMIN_NOMBRE", "Administradora"),
                             password=pwd, pin=pin)
            else:
                self.stdout.write("Falta ADMIN_PASSWORD / ADMIN_PIN: no se creó la administradora.")
        if not Categoria.objects.exists():
            call_command("cargar_menu")
