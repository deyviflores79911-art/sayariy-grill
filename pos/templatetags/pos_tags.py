from decimal import Decimal, InvalidOperation

from django import template

register = template.Library()


def formato_bs(valor, prefijo=True):
    """1250.5 -> 'Bs 1.250,50' (formato boliviano)."""
    try:
        v = Decimal(valor or 0)
    except (InvalidOperation, TypeError, ValueError):
        return valor
    s = f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"Bs {s}" if prefijo else s


@register.filter
def bs(valor):
    return formato_bs(valor)


@register.filter
def num(valor):
    return formato_bs(valor, prefijo=False)


@register.filter
def fecha(valor):
    from django.utils import timezone
    if not valor:
        return ""
    if hasattr(valor, "hour"):
        return timezone.localtime(valor).strftime("%d/%m/%Y %H:%M")
    return valor.strftime("%d/%m/%Y")
