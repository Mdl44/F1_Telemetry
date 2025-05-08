import os
from .settings import *

DEBUG = False
SECRET_KEY = 'django-insecure-829w_x8$=t_4p$&e#)r(=yz(31$sg0v%risyx#^h*w1)!#-c26'

ALLOWED_HOSTS = ['164.90.168.221', 'localhost', '127.0.0.1'] #schimba


DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'f1_telemetry',
        'USER': 'madalin',
        'PASSWORD': 'madalin',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}


STATIC_ROOT = os.path.join(BASE_DIR, 'static')
STATIC_URL = '/static/'

MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
MEDIA_URL = '/media/'