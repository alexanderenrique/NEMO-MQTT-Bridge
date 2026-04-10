"""
Bridge diagnostics persisted on MQTTBridgeStatus (cross-process visibility).
"""

from django.test import TestCase, Client
from django.contrib.auth.models import User

from NEMO_mqtt_bridge.models import MQTTBridgeStatus
from NEMO_mqtt_bridge.utils import (
    mqtt_bridge_status_payload,
    read_mqtt_bridge_diagnostics,
    update_mqtt_bridge_diagnostics,
)


class MqttBridgeDiagnosticsPersistenceTest(TestCase):
    def test_update_then_read_round_trip_via_db(self):
        fp = {"id": 42, "updated_at": "2026-04-09T12:00:00"}
        update_mqtt_bridge_diagnostics(
            {
                "last_reload_reason": "config_poll",
                "applied_fingerprint": fp,
                "last_error": "",
            }
        )
        data = read_mqtt_bridge_diagnostics()
        self.assertEqual(data.get("last_reload_reason"), "config_poll")
        self.assertEqual(data.get("applied_fingerprint"), fp)
        self.assertIn("diagnostics_updated_at", data)

        row = MQTTBridgeStatus.objects.get(key="default")
        self.assertEqual(row.bridge_diagnostics.get("last_reload_reason"), "config_poll")
        self.assertEqual(row.bridge_diagnostics.get("applied_fingerprint"), fp)

    def test_bridge_status_json_includes_diagnostics(self):
        user = User.objects.create_user(
            username="diaguser",
            email="d@example.com",
            password="x",
        )
        update_mqtt_bridge_diagnostics({"last_reload_reason": "notify"})
        client = Client()
        client.login(username="diaguser", password="x")
        response = client.get("/mqtt/mqtt_bridge_status/")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["diagnostics"]["last_reload_reason"], "notify")

    def test_mqtt_bridge_status_payload_matches_json_view(self):
        user = User.objects.create_user(
            username="payloaduser",
            email="p@example.com",
            password="x",
        )
        update_mqtt_bridge_diagnostics({"last_reload_reason": "notify"})
        client = Client()
        client.login(username="payloaduser", password="x")
        from_api = client.get("/mqtt/mqtt_bridge_status/").json()
        from_util = mqtt_bridge_status_payload()
        self.assertEqual(from_api.keys(), from_util.keys())
        self.assertEqual(from_api["diagnostics"], from_util["diagnostics"])
