"""Tests for AUTO-mode cleanup (pkill gated behind NEMO_MQTT_BRIDGE_DEV_PKILL)."""

from unittest.mock import patch

from NEMO_mqtt_bridge.bridge.auto_services import cleanup_existing_services


def test_cleanup_default_does_not_pkill(monkeypatch):
    monkeypatch.delenv("NEMO_MQTT_BRIDGE_DEV_PKILL", raising=False)
    with patch("NEMO_mqtt_bridge.bridge.auto_services.subprocess.run") as run:
        cleanup_existing_services(None)
        run.assert_not_called()


def test_cleanup_with_dev_pkill_calls_subprocess(monkeypatch):
    monkeypatch.setenv("NEMO_MQTT_BRIDGE_DEV_PKILL", "1")
    with patch("NEMO_mqtt_bridge.bridge.auto_services.subprocess.run") as run:
        cleanup_existing_services(None)
        run.assert_called_once()
        args, _ = run.call_args
        assert args[0][:2] == ["pkill", "-f"]
