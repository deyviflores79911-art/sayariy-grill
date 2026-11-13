from django.conf import settings
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.static import serve

urlpatterns = [
    path("django-admin/", admin.site.urls),
    path("", include("pos.urls")),
]

# Fotos de productos en disco (red local). En la nube vienen de Azure Blob Storage.
if not settings.AZURE_CONEXION:
    urlpatterns.append(re_path(r"^media/(?P<path>.*)$", serve, {"document_root": settings.MEDIA_ROOT}))
