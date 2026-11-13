# Sayariy Grill – Punto de venta (POS)

Sistema de punto de venta en Django para el restaurante. Moneda: Bolivianos (Bs).

## Uso diario (en la PC del restaurante)
1. Doble clic en **`iniciar.bat`** y no cerrar esa ventana.
2. En la tablet (conectada al mismo WiFi) abrir `http://IP-DE-LA-PC:8000`.
   La IP se ve con `ipconfig` → "Dirección IPv4". En Chrome: menú → "Agregar a pantalla principal".
3. Al cerrar el día: doble clic en **`respaldar.bat`** y copiar la carpeta `respaldos` a un USB o Google Drive.

## Acceso inicial
| Quién | Cómo entra |
|---|---|
| Administradora | contraseña `cambiar123` · PIN para autorizar anulaciones `0000` → **cámbielos en Personal** |
| Juan (ejemplo) | PIN `1234` |

Los productos de ejemplo se pueden editar o desactivar desde **Productos**.

## Instalación desde cero (otra PC)
```
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python manage.py migrate
.venv\Scripts\python manage.py crear_admin
.venv\Scripts\python manage.py datos_demo      (opcional)
```
Desarrollo: `.venv\Scripts\python manage.py runserver 0.0.0.0:8000` · Pruebas: `.venv\Scripts\python manage.py test pos`

## Reglas del negocio implementadas
- No se puede vender sin caja abierta; cada trabajador abre su propia caja.
- Cierre: efectivo esperado = monto inicial + ventas en efectivo − gastos pagados con esa caja.
- El nombre y el precio del producto se copian en cada venta (cambiar precios no altera ventas antiguas).
- Anular exige motivo; un trabajador además necesita el PIN de la administradora. Nada se borra.
- 5 intentos fallidos de PIN bloquean a ese usuario por 5 minutos.

## Pendiente (versión 2)
Inventario (stock, alertas, entradas de mercadería) e impresora térmica de tickets.
Los campos de stock ya existen en la base de datos.
