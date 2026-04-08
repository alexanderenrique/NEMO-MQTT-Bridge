"""
Tests for MQTT configuration fingerprinting and reload decision logic.
"""
from unittest.mock import patch

import pytest
from django.core.exceptions import ValidationError

from NEMO_mqtt_bridge.models import MQTTConfiguration
from NEMO_mqtt_bridge.postgres_mqtt_bridge import (
    mqtt_config_reload_needed,
    read_mqtt_config_fingerprint,
)


@pytest.mark.django_db
def test_read_mqtt_config_fingerprint_none_when_only_disabled():
    MQTTConfiguration.objects.create(name="off", enabled=False)
    assert read_mqtt_config_fingerprint() is None


@pytest.mark.django_db
def test_read_mqtt_config_fingerprint_returns_id_and_updated_at(mqtt_config):
    fp = read_mqtt_config_fingerprint()
    assert fp is not None
    cfg_id, updated_at = fp
    assert cfg_id == mqtt_config.id
    assert updated_at is not None


@pytest.mark.django_db
def test_read_mqtt_config_fingerprint_updates_after_save(mqtt_config):
    fp_before = read_mqtt_config_fingerprint()
    mqtt_config.broker_host = "other.example"
    mqtt_config.save()
    fp_after = read_mqtt_config_fingerprint()
    assert fp_before is not None and fp_after is not None
    assert mqtt_config_reload_needed(fp_before, fp_after)


def test_mqtt_config_reload_needed_same_none():
    assert not mqtt_config_reload_needed(None, None)


def test_mqtt_config_reload_needed_none_to_tuple():
    assert mqtt_config_reload_needed(None, (1, "t"))


def test_mqtt_config_reload_needed_tuple_inequality():
    assert mqtt_config_reload_needed((1, "a"), (1, "b"))
    assert not mqtt_config_reload_needed((1, "a"), (1, "a"))


@pytest.mark.django_db
def test_post_delete_mqtt_configuration_notifies_bridge():
    cfg = MQTTConfiguration.objects.create(
        name="to_delete",
        enabled=True,
        broker_host="localhost",
        broker_port=1883,
        qos_level=1,
        retain_messages=False,
    )
    with patch("NEMO_mqtt_bridge.db_publisher.notify_bridge_reload_config") as mock_notify:
        cfg.delete()
    mock_notify.assert_called_once()


@pytest.mark.django_db
def test_only_one_enabled_mqttconfiguration_allowed():
    MQTTConfiguration.objects.create(
        name="first",
        enabled=True,
        broker_host="localhost",
        broker_port=1883,
        qos_level=1,
        retain_messages=False,
    )
    cfg2 = MQTTConfiguration(
        name="second",
        enabled=True,
        broker_host="localhost",
        broker_port=1883,
        qos_level=1,
        retain_messages=False,
    )
    with pytest.raises(ValidationError):
        cfg2.full_clean()
