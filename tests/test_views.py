"""
Tests for NEMO MQTT Plugin views (mqtt_monitor, mqtt_monitor_api).
"""
import json
from unittest.mock import patch

from django.test import TestCase, Client
from django.contrib.auth.models import User

from NEMO_mqtt.models import MQTTConfiguration


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
        response = self.client.get("/mqtt/monitor/")
        self.assertEqual(response.status_code, 302)  # Redirect to login

    def test_mqtt_monitor_authenticated(self):
        """Test MQTT monitor page with authenticated user"""
        self.client.login(username="testuser", password="testpass123")
        response = self.client.get("/mqtt/monitor/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"NEMO MQTT Monitor", response.content)

    def test_mqtt_monitor_api_requires_login(self):
        """Test that MQTT monitor API requires login"""
        response = self.client.get("/mqtt/monitor/api/")
        self.assertEqual(response.status_code, 302)  # Redirect to login

    @patch("NEMO_mqtt.redis_publisher.redis_publisher")
    def test_mqtt_monitor_api_returns_messages(self, mock_redis_publisher):
        """Test MQTT monitor API returns messages from Redis"""
        mock_redis_publisher.get_monitor_messages.return_value = [
            {
                "id": 1,
                "timestamp": "2024-01-15T10:30:00Z",
                "source": "Redis",
                "topic": "nemo/tools/1/start",
                "payload": '{"event": "tool_usage_start"}',
                "qos": 1,
                "retain": False,
            }
        ]
        mock_redis_publisher.get_bridge_status.return_value = "connected"

        self.client.login(username="testuser", password="testpass123")
        response = self.client.get("/mqtt/monitor/api/")

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(len(data["messages"]), 1)
        self.assertEqual(data["count"], 1)
        self.assertTrue(data["monitoring"])
        self.assertEqual(data["broker_connected"], "connected")
        self.assertEqual(data["messages"][0]["topic"], "nemo/tools/1/start")

    @patch("NEMO_mqtt.redis_publisher.redis_publisher")
    def test_mqtt_monitor_api_empty_messages(self, mock_redis_publisher):
        """Test MQTT monitor API when no messages in Redis"""
        mock_redis_publisher.get_monitor_messages.return_value = []
        mock_redis_publisher.get_bridge_status.return_value = None

        self.client.login(username="testuser", password="testpass123")
        response = self.client.get("/mqtt/monitor/api/")

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["messages"], [])
        self.assertEqual(data["count"], 0)
        self.assertTrue(data["monitoring"])

    @patch("NEMO_mqtt.redis_publisher.redis_publisher")
    def test_mqtt_monitor_api_handles_exception(self, mock_redis_publisher):
        """Test MQTT monitor API handles Redis errors gracefully"""
        mock_redis_publisher.get_monitor_messages.side_effect = Exception("Redis unavailable")

        self.client.login(username="testuser", password="testpass123")
        response = self.client.get("/mqtt/monitor/api/")

        self.assertEqual(response.status_code, 500)
        data = json.loads(response.content)
        self.assertEqual(data["messages"], [])
        self.assertEqual(data["count"], 0)
        self.assertFalse(data["monitoring"])
        self.assertIn("error", data)
