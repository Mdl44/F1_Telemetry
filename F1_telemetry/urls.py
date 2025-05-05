from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('users/', include('f1_users.urls')),
    path('', include('f1_dashboard.urls')),
    path('analysis/', include('f1_analysis.urls')),
]