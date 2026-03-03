"""
Test-specific app configuration that doesn't load signals
"""
from django.apps import AppConfig


class MqttTestConfig(AppConfig):
    """Test configuration for NEMO MQTT Plugin that doesn't load signals"""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'NEMO_mqtt'
    
    def ready(self):
        """Don't load signals during testing to avoid NEMO dependencies"""
        pass
