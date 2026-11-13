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


from django.test import override_settings  # noqa: E402

from .models import Dispositivo  # noqa: E402


@override_settings(REQUIERE_DISPOSITIVO=True)
class DispositivoTests(TestCase):
    def setUp(self):
        cache.clear()
        self.admin = Usuario.objects.create(username="admin", first_name="Dueña", rol=Usuario.ADMIN)
        self.admin.set_password("secreto123")
        self.admin.set_pin("9999")
        self.admin.save()
        self.juan = Usuario.objects.create(username="juan", first_name="Juan")
        self.juan.set_pin("1234")
        self.juan.save()

    def test_equipo_no_autorizado_no_ve_pin(self):
        r = self.client.get(reverse("login"))
        self.assertRedirects(r, reverse("equipo"))
        r = self.client.post(reverse("login"), {"usuario_id": self.juan.pk, "pin": "1234"})
        self.assertRedirects(r, reverse("equipo"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_autorizar_equipo_y_luego_pin(self):
        r = self.client.post(reverse("equipo"), {"usuario": "admin", "password": "secreto123",
                                                 "autorizar": "on", "nombre": "Tablet caja"})
        self.assertRedirects(r, reverse("inicio"), fetch_redirect_response=False)
        self.assertIn(Dispositivo.COOKIE, r.cookies)
        d = Dispositivo.objects.get()
        self.assertEqual(d.nombre, "Tablet caja")
        self.assertNotEqual(d.token_hash, r.cookies[Dispositivo.COOKIE].value)  # se guarda cifrado
        self.client.post(reverse("logout"))
        r = self.client.post(reverse("login"), {"usuario_id": self.juan.pk, "pin": "1234"})
        self.assertRedirects(r, reverse("inicio"), fetch_redirect_response=False)
        # Revocado: el trabajador queda fuera
        d.activo = False
        d.save()
        self.assertRedirects(self.client.get(reverse("venta")), reverse("equipo"))

    def test_admin_sin_autorizar_puede_entrar(self):
        r = self.client.post(reverse("equipo"), {"usuario": "admin", "password": "secreto123"})
        self.assertRedirects(r, reverse("inicio"), fetch_redirect_response=False)
        self.assertEqual(Dispositivo.objects.count(), 0)
        self.assertEqual(self.client.get(reverse("panel")).status_code, 200)

    def test_trabajador_no_puede_autorizar_y_bloqueo(self):
        r = self.client.post(reverse("equipo"), {"usuario": "juan", "password": "1234", "autorizar": "on"})
        self.assertContains(r, "incorrectos")
        for _ in range(5):
            self.client.post(reverse("equipo"), {"usuario": "admin", "password": "mal"})
        r = self.client.post(reverse("equipo"), {"usuario": "admin", "password": "secreto123"})
        self.assertContains(r, "Demasiados intentos")


class CocinaTests(TestCase):
    def setUp(self):
        cache.clear()
        self.cajera = Usuario.objects.create(username="graciela", first_name="Graciela")
        self.cajera.set_pin("1111")
        self.cajera.save()
        self.cocinero = Usuario.objects.create(username="cocina", first_name="Cocinero", rol=Usuario.COCINA)
        self.cocinero.set_pin("2222")
        self.cocinero.save()
        platos = Categoria.objects.create(nombre="Platos")
        sodas = Categoria.objects.create(nombre="Sodas", a_cocina=False)
        self.pollo = Producto.objects.create(nombre="Cuarto pecho", categoria=platos, precio=Decimal("30"))
        self.soda = Producto.objects.create(nombre="Soda personal", categoria=sodas, precio=Decimal("7"))

    def vender(self, items, **extra):
        data = {"items": items, "tipo": "llevar", "metodo": "qr"}
        data.update(extra)
        return self.client.post(reverse("venta_confirmar"), json.dumps(data), content_type="application/json")

    def test_flujo_cocina(self):
        self.client.force_login(self.cajera)
        self.client.post(reverse("caja_abrir"), {"monto_inicial": "0"})
        self.vender([{"id": self.pollo.pk, "cantidad": 1, "nota": "sin arroz"}, {"id": self.soda.pk, "cantidad": 1}],
                    cliente="Doña Rosa", nota="todo para llevar")
        self.vender([{"id": self.soda.pk, "cantidad": 2}])  # solo bebida: no va a cocina
        con_plato, solo_soda = Venta.objects.order_by("pk")
        self.assertEqual(con_plato.cliente, "Doña Rosa")
        self.assertEqual(con_plato.nota, "todo para llevar")
        self.assertEqual(con_plato.cocina_estado, Venta.PENDIENTE)
        self.assertEqual(solo_soda.cocina_estado, Venta.LISTO)
        self.assertContains(self.client.get(reverse("ticket", args=[con_plato.pk])), "Doña Rosa")

        self.client.force_login(self.cocinero)
        self.assertRedirects(self.client.get(reverse("inicio")), reverse("cocina"), fetch_redirect_response=False)
        self.assertRedirects(self.client.get(reverse("venta")), reverse("cocina"))
        self.assertRedirects(self.client.get(reverse("reportes")), reverse("inicio"), fetch_redirect_response=False)
        d = self.client.get(reverse("cocina_pedidos")).json()
        self.assertEqual([p["id"] for p in d["pendientes"]], [con_plato.pk])
        pedido = d["pendientes"][0]
        self.assertEqual(pedido["cliente"], "Doña Rosa")
        self.assertEqual(pedido["items"], [{"cant": 1, "nombre": "Cuarto pecho", "nota": "sin arroz"}])  # sin la soda

        self.client.post(reverse("cocina_listo", args=[con_plato.pk]))
        con_plato.refresh_from_db()
        self.assertEqual(con_plato.cocina_estado, Venta.LISTO)
        self.assertEqual(con_plato.listo_por, self.cocinero)
        d = self.client.get(reverse("cocina_pedidos")).json()
        self.assertEqual(d["pendientes"], [])
        self.assertEqual([p["id"] for p in d["listos"]], [con_plato.pk])
        self.client.post(reverse("cocina_deshacer", args=[con_plato.pk]))
        self.assertEqual(len(self.client.get(reverse("cocina_pedidos")).json()["pendientes"]), 1)

    def test_venta_anulada_sale_de_cocina(self):
        self.client.force_login(self.cajera)
        self.client.post(reverse("caja_abrir"), {"monto_inicial": "0"})
        self.vender([{"id": self.pollo.pk, "cantidad": 1}])
        Venta.objects.get().anular("error", por=self.cajera)
        self.assertEqual(self.client.get(reverse("cocina_pedidos")).json()["pendientes"], [])


class PanelVivoTests(TestCase):
    def test_panel_en_vivo(self):
        cache.clear()
        admin = Usuario.objects.create(username="admin", first_name="Gabriela", rol=Usuario.ADMIN)
        cajera = Usuario.objects.create(username="graciela", first_name="Graciela")
        cat = Categoria.objects.create(nombre="Comida")
        pollo = Producto.objects.create(nombre="Cuarto pecho", categoria=cat, precio=Decimal("30"))
        self.client.force_login(cajera)
        self.client.post(reverse("caja_abrir"), {"monto_inicial": "0"})
        self.client.post(reverse("venta_confirmar"), json.dumps({
            "items": [{"id": pollo.pk, "cantidad": 2}], "tipo": "llevar", "metodo": "qr", "cliente": "Rosa"}),
            content_type="application/json")
        self.assertEqual(self.client.get(reverse("panel_vivo")).status_code, 302)  # solo administradora
        self.client.force_login(admin)
        self.assertEqual(self.client.get(reverse("panel")).status_code, 200)
        d = self.client.get(reverse("panel_vivo")).json()
        self.assertEqual(d["num"], 1)
        v = d["ventas"][0]
        self.assertEqual((v["vendedor"], v["cliente"], v["items"], v["cocina"]), ("Graciela", "Rosa", "2× Cuarto pecho", "pendiente"))
        self.assertEqual(d["por_vendedor"][0]["nombre"], "Graciela")
        self.assertEqual(d["cajas"][0]["nombre"], "Graciela")
