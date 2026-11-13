from decimal import Decimal

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import Q, Sum
from django.utils import timezone

CERO = Decimal("0.00")


class Usuario(AbstractUser):
    ADMIN = "admin"
    TRABAJADOR = "trabajador"
    ROLES = [(ADMIN, "Administrador"), (TRABAJADOR, "Trabajador")]

    rol = models.CharField(max_length=20, choices=ROLES, default=TRABAJADOR)
    pin = models.CharField("PIN (cifrado)", max_length=128, blank=True)

    class Meta:
        verbose_name = "usuario"

    def set_pin(self, pin):
        self.pin = make_password(pin)

    def check_pin(self, pin):
        return bool(self.pin) and check_password(pin, self.pin)

    @property
    def es_admin(self):
        return self.rol == self.ADMIN

    @property
    def nombre(self):
        return self.first_name or self.username

    def turno_abierto(self):
        return self.turnos.filter(estado=TurnoCaja.ABIERTA).first()

    def __str__(self):
        return self.nombre


class Configuracion(models.Model):
    nombre_negocio = models.CharField(max_length=100, default="Sayariy Grill")
    num_mesas = models.PositiveSmallIntegerField("número de mesas", default=10)
    pie_ticket = models.CharField("mensaje al pie del ticket", max_length=200, default="¡Gracias por su preferencia!")

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return self.nombre_negocio


class Categoria(models.Model):
    nombre = models.CharField(max_length=60, unique=True)
    orden = models.PositiveSmallIntegerField(default=0, help_text="Menor número aparece primero")
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ["orden", "nombre"]

    def __str__(self):
        return self.nombre


class Producto(models.Model):
    nombre = models.CharField(max_length=100)
    categoria = models.ForeignKey(Categoria, on_delete=models.PROTECT, related_name="productos")
    precio = models.DecimalField(max_digits=10, decimal_places=2)
    foto = models.ImageField(upload_to="productos/", blank=True)
    activo = models.BooleanField(default=True)
    # Inventario (versión 2)
    controla_stock = models.BooleanField(default=False)
    stock_actual = models.IntegerField(default=0)
    stock_minimo = models.IntegerField(default=0)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["categoria__orden", "precio", "nombre"]

    def __str__(self):
        return self.nombre


class TurnoCaja(models.Model):
    ABIERTA = "abierta"
    CERRADA = "cerrada"
    ESTADOS = [(ABIERTA, "Abierta"), (CERRADA, "Cerrada")]

    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="turnos")
    abierto_en = models.DateTimeField(default=timezone.now)
    monto_inicial = models.DecimalField(max_digits=10, decimal_places=2)
    cerrado_en = models.DateTimeField(null=True, blank=True)
    # Valores fijados al cierre
    ventas_efectivo = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    ventas_qr = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    ventas_tarjeta = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    gastos_caja = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    efectivo_esperado = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    efectivo_declarado = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    diferencia = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    observacion = models.TextField(blank=True)
    estado = models.CharField(max_length=10, choices=ESTADOS, default=ABIERTA)

    class Meta:
        ordering = ["-abierto_en"]
        constraints = [
            models.UniqueConstraint(
                fields=["usuario"], condition=Q(estado="abierta"), name="un_turno_abierto_por_usuario"
            )
        ]

    def calcular(self):
        """Totales actuales del turno (ventas válidas y gastos pagados con la caja)."""
        por_metodo = {m: CERO for m, _ in Venta.METODOS}
        filas = self.ventas.filter(estado=Venta.VALIDA).values("metodo_pago").annotate(s=Sum("total"))
        for f in filas:
            por_metodo[f["metodo_pago"]] = f["s"] or CERO
        gastos = self.gastos.aggregate(s=Sum("monto"))["s"] or CERO
        return {
            "efectivo": por_metodo[Venta.EFECTIVO],
            "qr": por_metodo[Venta.QR],
            "tarjeta": por_metodo[Venta.TARJETA],
            "total": sum(por_metodo.values(), CERO),
            "gastos": gastos,
            "efectivo_esperado": self.monto_inicial + por_metodo[Venta.EFECTIVO] - gastos,
            "num_ventas": self.ventas.filter(estado=Venta.VALIDA).count(),
            "num_anuladas": self.ventas.filter(estado=Venta.ANULADA).count(),
        }

    def cerrar(self, efectivo_declarado, observacion=""):
        c = self.calcular()
        self.ventas_efectivo = c["efectivo"]
        self.ventas_qr = c["qr"]
        self.ventas_tarjeta = c["tarjeta"]
        self.gastos_caja = c["gastos"]
        self.efectivo_esperado = c["efectivo_esperado"]
        self.efectivo_declarado = efectivo_declarado
        self.diferencia = efectivo_declarado - c["efectivo_esperado"]
        self.observacion = observacion
        self.cerrado_en = timezone.now()
        self.estado = self.CERRADA
        self.save()

    @property
    def total_ventas(self):
        return (self.ventas_efectivo or CERO) + (self.ventas_qr or CERO) + (self.ventas_tarjeta or CERO)

    def __str__(self):
        return f"Caja #{self.pk} – {self.usuario}"


class Venta(models.Model):
    EFECTIVO = "efectivo"
    QR = "qr"
    TARJETA = "tarjeta"
    METODOS = [(EFECTIVO, "Efectivo"), (QR, "QR"), (TARJETA, "Tarjeta")]
    MESA = "mesa"
    LLEVAR = "llevar"
    TIPOS = [(MESA, "Mesa"), (LLEVAR, "Para llevar")]
    VALIDA = "valida"
    ANULADA = "anulada"
    ESTADOS = [(VALIDA, "Válida"), (ANULADA, "Anulada")]

    turno = models.ForeignKey(TurnoCaja, on_delete=models.PROTECT, related_name="ventas")
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="ventas")
    fecha_hora = models.DateTimeField(default=timezone.now, db_index=True)
    tipo = models.CharField(max_length=10, choices=TIPOS, default=LLEVAR)
    mesa = models.PositiveSmallIntegerField(null=True, blank=True)
    metodo_pago = models.CharField(max_length=10, choices=METODOS)
    total = models.DecimalField(max_digits=12, decimal_places=2)
    monto_recibido = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    cambio = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    estado = models.CharField(max_length=10, choices=ESTADOS, default=VALIDA, db_index=True)
    motivo_anulacion = models.TextField(blank=True)
    anulada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    autorizada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    anulada_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-fecha_hora"]

    @property
    def numero(self):
        return f"{self.pk:06d}"

    @property
    def destino(self):
        return f"Mesa {self.mesa}" if self.tipo == self.MESA else "Para llevar"

    @property
    def anulada(self):
        return self.estado == self.ANULADA

    def anular(self, motivo, por, autorizada_por=None):
        self.estado = self.ANULADA
        self.motivo_anulacion = motivo
        self.anulada_por = por
        self.autorizada_por = autorizada_por or por
        self.anulada_en = timezone.now()
        self.save()

    def __str__(self):
        return f"Venta {self.numero}"


class VentaItem(models.Model):
    venta = models.ForeignKey(Venta, on_delete=models.CASCADE, related_name="items")
    producto = models.ForeignKey(Producto, on_delete=models.SET_NULL, null=True, related_name="+")
    # Copia fija del momento de la venta
    nombre_producto = models.CharField(max_length=100)
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    cantidad = models.PositiveIntegerField()
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)
    nota = models.CharField(max_length=200, blank=True)

    def __str__(self):
        return f"{self.cantidad} x {self.nombre_producto}"


class Gasto(models.Model):
    fecha = models.DateField(default=timezone.localdate, db_index=True)
    descripcion = models.CharField("descripción", max_length=200)
    monto = models.DecimalField(max_digits=10, decimal_places=2)
    turno = models.ForeignKey(
        TurnoCaja, on_delete=models.PROTECT, null=True, blank=True, related_name="gastos",
        verbose_name="pagado con la caja de",
    )
    registrado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fecha", "-creado_en"]

    def __str__(self):
        return f"{self.descripcion} ({self.monto})"
