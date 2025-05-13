"""
ASGI config for F1_telemetry project.(Asynchronous Server Gateway Interface)

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

import os # variabile de mediu

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'F1_telemetry.settings') # unde sa caute Django pentru fisierul de conf

application = get_asgi_application()
