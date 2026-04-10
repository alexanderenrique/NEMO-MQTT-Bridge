"""
Server-side context for the MQTT monitor page (no NEMO customization imports).
"""

from .models import MQTTConfiguration, MQTTEventQueue, MQTTMessageLog

_MQTT_CONFIG_DEFAULTS = {
    "name": "Default MQTT Configuration",
    "enabled": False,
    "broker_host": "localhost",
    "broker_port": 1883,
    "topic_prefix": "nemo/",
    "qos_level": 1,
    "retain_messages": False,
    "clean_session": True,
    "auto_reconnect": True,
    "reconnect_delay": 5,
    "max_reconnect_attempts": 10,
    "log_messages": True,
    "log_level": "INFO",
}


def mqtt_config_context() -> dict:
    """Context for the MQTT customization form (config row + plugin version)."""
    try:
        from . import __version__ as plugin_version
    except Exception:
        plugin_version = None

    import os
    import socket

    unique_client_id = f"nemo_{socket.gethostname()}_{os.getpid()}"
    defaults = {**_MQTT_CONFIG_DEFAULTS, "client_id": unique_client_id}
    config, _created = MQTTConfiguration.objects.get_or_create(defaults=defaults)

    return {
        "config": config,
        "plugin_version": plugin_version,
    }


def mqtt_dashboard_context() -> dict:
    """Full monitor context: config plus queue samples, bridge status, and heartbeats."""
    ctx = mqtt_config_context()

    recent_messages = MQTTMessageLog.objects.order_by("-sent_at")[:5]
    pending_queue_count = MQTTEventQueue.objects.filter(processed=False).count()
    pending_queue_oldest = (
        MQTTEventQueue.objects.filter(processed=False)
        .order_by("created_at")
        .values_list("created_at", flat=True)
        .first()
    )
    pending_queue_newest = (
        MQTTEventQueue.objects.filter(processed=False)
        .order_by("-created_at")
        .values_list("created_at", flat=True)
        .first()
    )
    recent_queue_events = (
        MQTTEventQueue.objects.order_by("-id").values(
            "id", "topic", "qos", "retain", "processed", "created_at"
        )[:5]
    )
    try:
        from .db_publisher import db_publisher

        bridge_status = db_publisher.get_bridge_status()
    except Exception:
        bridge_status = None

    bridge_last_heartbeat_iso = None
    try:
        from .models import MQTTBridgeStatus

        hb_row = MQTTBridgeStatus.objects.filter(key="default").first()
        if hb_row and hb_row.last_heartbeat:
            bridge_last_heartbeat_iso = hb_row.last_heartbeat.isoformat()
    except Exception:
        pass

    ctx.update(
        {
            "recent_messages": recent_messages,
            "bridge_status": bridge_status,
            "bridge_last_heartbeat_iso": bridge_last_heartbeat_iso,
            "pending_queue_count": pending_queue_count,
            "pending_queue_oldest": pending_queue_oldest,
            "pending_queue_newest": pending_queue_newest,
            "recent_queue_events": list(recent_queue_events),
        }
    )
    return ctx
