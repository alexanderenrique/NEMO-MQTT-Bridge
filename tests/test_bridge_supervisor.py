"""Tests for bridge_supervisor and heartbeat helpers."""

import fcntl
from datetime import timedelta
import pytest
from django.utils import timezone

from NEMO_mqtt_bridge.bridge_supervisor import _heartbeat_stale, _supervisor_acquire_lock
from NEMO_mqtt_bridge.models import MQTTBridgeStatus


def test_supervisor_lock_conflict_exits(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "NEMO_mqtt_bridge.bridge_supervisor.SUPERVISOR_LOCK_PATH",
        str(tmp_path / "supervisor.lock"),
    )
    hold = open(tmp_path / "supervisor.lock", "w")
    fcntl.flock(hold.fileno(), fcntl.LOCK_EX)
    try:
        with pytest.raises(SystemExit) as exc:
            _supervisor_acquire_lock()
        assert exc.value.code == 1
    finally:
        fcntl.flock(hold.fileno(), fcntl.LOCK_UN)
        hold.close()


@pytest.mark.django_db
def test_heartbeat_stale_false_when_missing_row():
    assert _heartbeat_stale(90) is False


@pytest.mark.django_db
def test_heartbeat_stale_false_when_null_heartbeat():
    MQTTBridgeStatus.objects.create(key="default", status="disconnected")
    assert _heartbeat_stale(90) is False


@pytest.mark.django_db
def test_heartbeat_stale_true_when_old():
    old = timezone.now() - timedelta(seconds=200)
    MQTTBridgeStatus.objects.create(
        key="default", status="connected", last_heartbeat=old
    )
    assert _heartbeat_stale(90) is True


@pytest.mark.django_db
def test_heartbeat_stale_false_when_recent():
    MQTTBridgeStatus.objects.create(
        key="default",
        status="connected",
        last_heartbeat=timezone.now() - timedelta(seconds=10),
    )
    assert _heartbeat_stale(90) is False


@pytest.mark.django_db
def test_touch_bridge_heartbeat_updates_row():
    from NEMO_mqtt_bridge.postgres_mqtt_bridge import _touch_bridge_heartbeat

    _touch_bridge_heartbeat()
    row = MQTTBridgeStatus.objects.get(key="default")
    assert row.last_heartbeat is not None
