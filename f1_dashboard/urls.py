from django.urls import path
from . import views

app_name = 'f1_dashboard'

urlpatterns = [
    path('', views.index, name='index'),
    path('visualization/', views.visualization, name='visualization'),
    path('visualization/team/', views.team_view, name='team_view'),
    path('visualization/driver/', views.driver_view, name='driver_view'),
    path('visualization/events/', views.event_view, name='event_view'),
    path('visualization/entries/', views.entry_view, name='entry_view'),
    path('visualization/telemetry/', views.telemetry_view, name='telemetry_view'),
    path('visualization/qualifying-analysis/', views.qualifying_analysis_view, name='qualifying_analysis_view'),
    path('visualization/race-analysis/', views.race_analysis_view, name='race_analysis_view'),
    path('drivers/create/',views.driver_create, name = 'driver_create'),
    path('drivers/edit/<int:driver_id>/', views.driver_edit, name = 'driver_edit'),
    path('driver/delete/<int:driver_id>/', views.driver_delete, name = 'driver_delete'),
    path('telemetry/create/', views.telemetry_create, name='telemetry_create'),
    path('telemetry/edit/<int:telemetry_id>/', views.telemetry_edit, name='telemetry_edit'),
    path('telemetry/delete/<int:telemetry_id>/', views.telemetry_delete, name='telemetry_delete'),
]