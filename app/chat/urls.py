from django.urls import path
from app.chat import views

urlpatterns = [
    path('healthz', views.healthz, name='healthz'),
    path('readyz', views.readyz, name='readyz'),
    path('metrics', views.metrics, name='metrics'),
]