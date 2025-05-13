from django.urls import path
from . import views

app_name = 'f1_users'

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('profile/', views.profile_view, name='profile'),
    path('register/', views.register_view, name='register'),
    path('admin/dashboard/', views.admin_dashboard, name='admin_dashboard'),
    
    path('admin/users/', views.user_list, name='user_list'),
    path('admin/users/create/', views.user_create, name='user_create'),
    path('admin/users/<int:user_id>/edit/', views.user_edit, name='user_edit'),
    path('admin/users/<int:user_id>/delete/', views.user_delete, name='user_delete'),
]