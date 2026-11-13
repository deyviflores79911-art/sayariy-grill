from .models import Configuracion


def negocio(request):
    return {"config": Configuracion.get()}
