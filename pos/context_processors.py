from django.conf import settings

from .models import Configuracion


def negocio(request):
    return {"config": Configuracion.get(), "requiere_dispositivo": settings.REQUIERE_DISPOSITIVO}
