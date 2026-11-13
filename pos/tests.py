import json
from decimal import Decimal

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from .models import Categoria, Gasto, Producto, TurnoCaja, Usuario, Venta


class PosTests(TestCase):
    def setUp(self):
        cache.clear()
        self.admin = Usuario.objects.create(username="admin", first_name="Dueña", rol=Usuario.ADMIN)
        self.admin.set_password("secreto123")
        self.admin.set_pin("9999")
        self.admin.save()
        self.juan = Usuario.objects.create(username="juan", first_name="Juan")
        self.juan.set_pin("1234")
        self.juan.save()
        cat = Categoria.objects.create(nombre="Platos")
        self.pique = Producto.objects.create(nombre="Pique", categoria=cat, precio=Decimal("55.00"))
        self.coca = Producto.objects.create(nombre="Coca", categoria=cat, precio=Decimal("18.00"))

    def entrar_juan(self):
        return self.client.post(reverse("login"), {"usuario_id": self.juan.pk, "pin": "1234"})

    def vender(self, **extra):
        data = {"items": [{"id": self.pique.pk, "cantidad": 2, "nota": "sin cebolla"},
                          {"id": self.coca.pk, "cantidad": 1}],
                "tipo": "mesa", "mesa": 3, "metodo": "efectivo", "recibido": "200"}
        data.update(extra)
        return self.client.post(reverse("venta_confirmar"), json.dumps(data), content_type="application/json")

    def test_login_pin_y_bloqueo(self):
        self.assertRedirects(self.entrar_juan(), reverse("inicio"), fetch_redirect_response=False)
        self.client.logout()
        for _ in range(5):
            self.client.post(reverse("login"), {"usuario_id": self.juan.pk, "pin": "0000"})
        r = self.entrar_juan()  # PIN correcto, pero bloqueado
        self.assertContains(r, "Demasiados intentos")

    def test_admin_no_entra_con_pin(self):
        r = self.client.post(reverse("login"), {"usuario_id": self.admin.pk, "pin": "9999"})
        self.assertEqual(r.status_code, 200)
        r = self.client.post(reverse("login"), {"usuario_id": self.admin.pk, "password": "secreto123"})
        self.assertRedirects(r, reverse("inicio"), fetch_redirect_response=False)

    def test_no_vende_sin_caja(self):
        self.entrar_juan()
        self.assertRedirects(self.client.get(reverse("venta")), reverse("caja_abrir"))
        self.assertEqual(self.vender().status_code, 400)

    def test_venta_completa_y_cierre(self):
        self.entrar_juan()
        self.client.post(reverse("caja_abrir"), {"monto_inicial": "100"})
        r = self.vender()
        self.assertTrue(r.json()["ok"])
        v = Venta.objects.get()
        self.assertEqual(v.total, Decimal("128.00"))
        self.assertEqual(v.cambio, Decimal("72.00"))
        self.assertEqual(v.items.get(nombre_producto="Pique").nota, "sin cebolla")
        # Cambiar el precio no altera la venta
        self.pique.precio = Decimal("60")
        self.pique.save()
        self.assertEqual(v.items.get(nombre_producto="Pique").precio_unitario, Decimal("55.00"))
        # QR y gasto pagado de la caja
        self.vender(metodo="qr", recibido=None, items=[{"id": self.coca.pk, "cantidad": 1}])
        turno = self.juan.turno_abierto()
        Gasto.objects.create(descripcion="Gas", monto=Decimal("20"), turno=turno, registrado_por=self.admin)
        r = self.client.post(reverse("caja_cerrar"), {"efectivo_declarado": "205", "observacion": ""})
        turno.refresh_from_db()
        self.assertEqual(turno.estado, TurnoCaja.CERRADA)
        self.assertEqual(turno.efectivo_esperado, Decimal("208.00"))  # 100 + 128 - 20
        self.assertEqual(turno.ventas_qr, Decimal("18.00"))
        self.assertEqual(turno.diferencia, Decimal("-3.00"))

    def test_efectivo_insuficiente(self):
        self.entrar_juan()
        self.client.post(reverse("caja_abrir"), {"monto_inicial": "0"})
        r = self.vender(recibido="50")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(Venta.objects.count(), 0)

    def test_anulacion_requiere_pin_admin(self):
        self.entrar_juan()
        self.client.post(reverse("caja_abrir"), {"monto_inicial": "0"})
        self.vender()
        v = Venta.objects.get()
        url = reverse("venta_anular", args=[v.pk])
        self.client.post(url, {"motivo": "cliente canceló", "pin_admin": "1111"})
        v.refresh_from_db()
        self.assertEqual(v.estado, Venta.VALIDA)
        self.client.post(url, {"motivo": "cliente canceló", "pin_admin": "9999"})
        v.refresh_from_db()
        self.assertEqual(v.estado, Venta.ANULADA)
        self.assertEqual(v.anulada_por, self.juan)
        self.assertEqual(v.autorizada_por, self.admin)
        self.assertEqual(self.juan.turno_abierto().calcular()["total"], Decimal("0"))

    def test_trabajador_no_ve_admin(self):
        self.entrar_juan()
        self.assertRedirects(self.client.get(reverse("reportes")), reverse("inicio"), fetch_redirect_response=False)

    def test_reportes_y_excel(self):
        self.entrar_juan()
        self.client.post(reverse("caja_abrir"), {"monto_inicial": "0"})
        self.vender()
        self.client.logout()
        self.client.force_login(self.admin)
        for nombre in ("panel", "reportes", "ventas", "cierres", "gastos", "productos", "categorias",
                       "trabajadores", "configuracion"):
            self.assertEqual(self.client.get(reverse(nombre)).status_code, 200, nombre)
        r = self.client.get(reverse("reportes") + "?periodo=mes")
        self.assertContains(r, "Pique")
        r = self.client.get(reverse("reportes_excel") + "?periodo=hoy")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.content.startswith(b"PK"))
