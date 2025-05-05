from django.urls import path
from . import views
#sunt mapate modelele url la view-uri
app_name = 'f1_analysis'

urlpatterns = [
    path('race/', views.race_analysis, name='race'),
    path('qualifying/', views.qualifying_analysis, name='qualifying'),
]