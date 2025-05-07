from django.urls import path
from . import views

app_name = 'f1_analysis'

urlpatterns = [
    path('qualifying/', views.qualifying_analysis, name='qualifying'),
    path('race/', views.race_analysis, name='race'),
    
    path('qualifying/get-drivers/', views.get_qualifying_drivers, name='get_qualifying_drivers'),
    path('qualifying/create/', views.create_qualifying_analysis, name='create_qualifying_analysis'),
    
    path('race/get-drivers/', views.get_race_drivers, name='get_race_drivers'),
    path('race/create/', views.create_race_analysis, name='create_race_analysis'),
]