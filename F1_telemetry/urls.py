from django.contrib import admin 
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
import os
#rute principale
urlpatterns = [
    path('admin/', admin.site.urls),
    path('users/', include('f1_users.urls')),
    path('', include('f1_dashboard.urls')),
    path('analysis/', include('f1_analysis.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    
    urlpatterns += static('/analysis/files/', document_root=os.path.join(settings.BASE_DIR, 'analysis'))