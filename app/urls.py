# app/urls.py
from django.urls import include, path

urlpatterns = [
    path('', include('chat.urls')),
    path('', include('django_prometheus.urls'))
]