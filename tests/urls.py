"""Test URL configuration - mirrors production: NEMO_mqtt under /mqtt/"""
from django.urls import path, include

urlpatterns = [
    path("mqtt/", include("NEMO_mqtt.urls")),
]
