#!/bin/bash
# Arranque en Azure App Service (Linux)
python manage.py migrate --noinput
python manage.py createcachetable
python manage.py inicializar
gunicorn --bind=0.0.0.0:8000 --workers 2 --timeout 120 --access-logfile - config.wsgi
