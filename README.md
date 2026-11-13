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

## En internet (Vercel + Azure)
- App: **https://sayariy-grill.vercel.app** (cada `git push` a `main` publica solo)
- Base de datos: Azure PostgreSQL `sayariy-grill-db` (Chile Central)
- Fotos de productos: Azure Blob Storage `sayariygrillfotos`, contenedor `media`
- Variables en Vercel → Settings → Environment Variables: `DATABASE_URL`, `DJANGO_SECRET_KEY`,
  `AZURE_STORAGE_CONNECTION_STRING`, `DJANGO_DEBUG=0`, `DJANGO_HTTPS=1`, `DJANGO_REQUIERE_DISPOSITIVO=0`,
  `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS`
- Las claves están en `secretos_azure.env` (solo en la PC, no se sube a GitHub).
- Migraciones tras cambiar modelos: con `DATABASE_URL` definida, ejecutar `python manage.py migrate`.
- Se puede entrar desde cualquier dispositivo. (Opcional: con `DJANGO_REQUIERE_DISPOSITIVO=1` solo los equipos autorizados en el menú **Equipos** muestran el ingreso con PIN.)
