from datetime import timedelta

from django.conf import settings
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.utils import timezone

from .models import Dispositivo

EXENTOS = ("/static/", "/media/", "/equipo/")


class DispositivoMiddleware:
    """Si REQUIERE_DISPOSITIVO está activo, solo los equipos autorizados pueden usar el POS.
    La administradora puede entrar desde cualquier equipo con usuario y contraseña."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.dispositivo = None
        if settings.REQUIERE_DISPOSITIVO:
            request.dispositivo = Dispositivo.desde_request(request)
            if not request.path.startswith(EXENTOS):
                d = request.dispositivo
                if d:
                    ahora = timezone.now()
                    if not d.ultimo_uso or ahora - d.ultimo_uso > timedelta(minutes=10):
                        Dispositivo.objects.filter(pk=d.pk).update(ultimo_uso=ahora)
                elif not (request.user.is_authenticated and request.user.es_admin):
                    if request.user.is_authenticated:
                        logout(request)
                    return redirect("equipo")
        return self.get_response(request)
