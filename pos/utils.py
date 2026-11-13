from io import BytesIO

from django.core.files.base import ContentFile
from PIL import Image, ImageOps


def comprimir_imagen(archivo, max_lado=800, calidad=82):
    """Reduce y convierte a JPEG las fotos subidas desde el celular."""
    img = Image.open(archivo)
    img = ImageOps.exif_transpose(img)
    if img.mode != "RGB":
        img = img.convert("RGB")
    img.thumbnail((max_lado, max_lado))
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=calidad, optimize=True)
    nombre = (archivo.name.rsplit(".", 1)[0] or "foto")[:60] + ".jpg"
    return ContentFile(buf.getvalue(), name=nombre)
