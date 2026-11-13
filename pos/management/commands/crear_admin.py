import getpass
import re

from django.core.management.base import BaseCommand, CommandError

from pos.models import Usuario


class Command(BaseCommand):
    help = "Crea (o actualiza) la cuenta de la administradora."

    def add_arguments(self, parser):
        parser.add_argument("--usuario", default="admin")
        parser.add_argument("--nombre")
        parser.add_argument("--password")
        parser.add_argument("--pin")

    def handle(self, *args, **o):
        nombre = o["nombre"] or input("Nombre de la administradora: ").strip() or "Administradora"
        password = o["password"] or getpass.getpass("Contraseña (mínimo 6 caracteres): ")
        pin = o["pin"] or getpass.getpass("PIN de 4 dígitos (para autorizar anulaciones): ")
        if len(password) < 6:
            raise CommandError("La contraseña debe tener al menos 6 caracteres.")
        if not re.fullmatch(r"\d{4}", pin):
            raise CommandError("El PIN debe tener 4 números.")
        u, creado = Usuario.objects.get_or_create(username=o["usuario"])
        u.first_name = nombre
        u.rol = Usuario.ADMIN
        u.is_active = True
        u.is_staff = u.is_superuser = True
        u.set_password(password)
        u.set_pin(pin)
        u.save()
        self.stdout.write(self.style.SUCCESS(
            f"Administradora {'creada' if creado else 'actualizada'}: {nombre} (usuario: {u.username})"))
