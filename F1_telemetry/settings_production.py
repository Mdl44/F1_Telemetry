import os
from .settings import *

DEBUG = False
SECRET_KEY = 'django-insecure-829w_x8$=t_4p$&e#)r(=yz(31$sg0v%risyx#^h*w1)!#-c26'

ALLOWED_HOSTS = ['164.90.168.221', 'localhost', '127.0.0.1']

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

STATICFILES_DIRS = []
STATIC_ROOT = '/www/f1telemetry/static'
STATIC_URL = '/static/'


MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
MEDIA_URL = '/media/'

ANALYSIS_FILES_DIR = os.path.join(BASE_DIR, 'analysis')
CSRF_COOKIE_SECURE = False
SESSION_COOKIE_SECURE = False

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]