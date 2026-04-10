"""
Tests for NEMO MQTT Plugin views (mqtt_monitor).
"""
from django.test import TestCase, Client
from django.contrib.auth.models import User

from NEMO_mqtt_bridge.models import MQTTBridgeStatus, MQTTConfiguration


class MQTTMonitorViewTest(TestCase):
    """Test MQTT monitor page and API views"""

    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )
        self.client = Client()
        MQTTConfiguration.objects.create(
            name="Test Config",
            enabled=True,
            broker_host="localhost",
            broker_port=1883,
        )

    def test_mqtt_monitor_requires_login(self):
        """Test that MQTT monitor page requires login"""
        response = self.client.get("/mqtt/mqtt_monitor/")
        self.assertEqual(response.status_code, 302)  # Redirect to login

    def test_mqtt_monitor_authenticated(self):
        """Test MQTT monitor page with authenticated user"""
        self.client.login(username="testuser", password="testpass123")
        response = self.client.get("/mqtt/mqtt_monitor/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"NEMO MQTT Monitor", response.content)
        self.assertIn(b"Status & Recent Messages", response.content)

    def test_mqtt_monitor_embeds_initial_bridge_status_json(self):
        """SSR json_script matches DB row so fields work before the first poll."""
        self.client.login(username="testuser", password="testpass123")
        MQTTBridgeStatus.objects.update_or_create(
            key="default",
            defaults={"status": "connected"},
        )
        response = self.client.get("/mqtt/mqtt_monitor/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'id="mqtt-bridge-initial-status"', response.content)
        self.assertIn(b'"status": "connected"', response.content)
        self.assertIn(b'"updated_at":', response.content)
