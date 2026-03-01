"""Test URL configuration - mirrors production: nemo_mqtt under /mqtt/"""
from django.urls import path, include

urlpatterns = [
    path("mqtt/", include("nemo_mqtt.urls")),
]
