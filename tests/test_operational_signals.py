#!/usr/bin/env python3
"""
Tests for operational / non-operational MQTT events driven by NEMO custom signals.

These tests exercise the NEMO_mqtt_bridge signal handlers by sending NEMO's
tool_enabled/tool_disabled signals and asserting that the DB publisher is called
with the correct topics and payloads.
"""

import os
import sys
from unittest import mock

import pytest


sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tests.test_settings")


@pytest.mark.django_db
def test_tool_operational_and_non_operational_events(monkeypatch):
    """
    Verify that tool_enabled/tool_disabled signals result in the expected
    MQTTEventQueue publications for operational status.
    """
    import django

    django.setup()

    from NEMO_mqtt_bridge import signals as mqtt_signals

    # Skip test gracefully if NEMO is not available in this environment
    if not mqtt_signals.NEMO_AVAILABLE or mqtt_signals.Tool is None:
        pytest.skip("NEMO not available; skipping operational signal tests")

    from NEMO.signals import tool_enabled, tool_disabled

    # Prepare a fake tool instance
    tool = mqtt_signals.Tool(id=55, name="Test Tool")

    # Patch db_publisher on the global signal_handler
    fake_publisher = mock.MagicMock()

    class FakeConfig:
        qos_level = 1
        retain_messages = False

    def fake_get_mqtt_config():
        return FakeConfig()

    mqtt_signals.signal_handler.db_publisher = fake_publisher

    # Patch _get_mqtt_config to avoid DB access
    monkeypatch.setattr(
        mqtt_signals.MQTTSignalHandler,
        "_get_mqtt_config",
        lambda self: fake_get_mqtt_config(),
    )

    # Fire tool_enabled (operational)
    tool_enabled.send(sender=mqtt_signals.Tool, instance=tool)

    # Fire tool_disabled (non-operational)
    tool_disabled.send(sender=mqtt_signals.Tool, instance=tool)

    # Collect topics from publish_event calls
    published_topics = [
        call.kwargs.get("topic") or call.args[0] for call in fake_publisher.publish_event.call_args_list
    ]

    assert f"nemo/tools/{tool.id}/operational" in published_topics
    assert f"nemo/tools/{tool.id}/non-operational" in published_topics

