"""
Utility functions for MQTT plugin.
"""

import json
import logging
from typing import Any, Dict, Optional, Tuple, TYPE_CHECKING
from django.conf import settings
from django.utils import timezone
from django.http import HttpResponse

if TYPE_CHECKING:
    from .models import MQTTConfiguration

logger = logging.getLogger(__name__)


def mqtt_config_safe_snapshot(config: Optional["MQTTConfiguration"]) -> Optional[Dict[str, Any]]:
    """
    Non-secret fields for DEBUG/INFO diagnostics (never password or HMAC secret).
    """
    if config is None:
        return None
    updated = getattr(config, "updated_at", None)
    return {
        "id": config.pk,
        "updated_at": updated.isoformat() if updated is not None else None,
        "enabled": bool(config.enabled),
        "broker_host": config.broker_host,
        "broker_port": config.broker_port,
        "username": config.username or None,
        "password_set": bool(getattr(config, "password", None)),
        "use_hmac": bool(getattr(config, "use_hmac", False)),
        "hmac_key_set": bool(getattr(config, "hmac_secret_key", None)),
        "client_id": getattr(config, "client_id", None),
        "keepalive": getattr(config, "keepalive", None),
    }


MQTT_BRIDGE_DIAGNOSTICS_CACHE_KEY = "mqtt_bridge_diagnostics"
MQTT_BRIDGE_DIAGNOSTICS_CACHE_TIMEOUT = 600


def mqtt_config_fingerprint_serial(
    fp: Optional[Tuple[Any, Any]],
) -> Optional[Dict[str, Any]]:
    """Serialize (id, updated_at) from DB for JSON/cache (no secrets)."""
    if fp is None:
        return None
    cid, updated_at = fp
    return {
        "id": cid,
        "updated_at": updated_at.isoformat() if updated_at is not None else None,
    }


def read_mqtt_bridge_diagnostics() -> Dict[str, Any]:
    """
    Prefer DB (singleton MQTTBridgeStatus row) so the web process sees updates
    from a separate bridge process; fall back to cache for older deployments/tests.
    """
    try:
        from .models import MQTTBridgeStatus

        row = MQTTBridgeStatus.objects.filter(key="default").first()
        if row is not None:
            raw = getattr(row, "bridge_diagnostics", None)
            if isinstance(raw, dict):
                return dict(raw)
    except Exception:
        logger.debug("read_mqtt_bridge_diagnostics: DB read failed", exc_info=True)

    from django.core.cache import cache

    raw = cache.get(MQTT_BRIDGE_DIAGNOSTICS_CACHE_KEY)
    return dict(raw) if isinstance(raw, dict) else {}


def mqtt_bridge_status_payload() -> Dict[str, Any]:
    """
    Same fields as the mqtt_bridge_status JSON view: bridge row + diagnostics.
    Used by the view and by the monitor page for SSR and polling consistency.
    """
    status = None
    updated_at = None
    last_heartbeat = None
    diagnostics: Dict[str, Any] = {}
    try:
        diagnostics = read_mqtt_bridge_diagnostics()
    except Exception:
        pass
    try:
        from .models import MQTTBridgeStatus

        row = MQTTBridgeStatus.objects.filter(key="default").first()
        if row:
            status = row.status
            updated_at = row.updated_at.isoformat() if row.updated_at else None
            if row.last_heartbeat:
                last_heartbeat = row.last_heartbeat.isoformat()
    except Exception:
        pass
    return {
        "status": status,
        "updated_at": updated_at,
        "last_heartbeat": last_heartbeat,
        "diagnostics": diagnostics,
    }


def update_mqtt_bridge_diagnostics(partial: Dict[str, Any]) -> None:
    from django.core.cache import cache
    from django.utils import timezone

    data = read_mqtt_bridge_diagnostics()
    data.update(partial)
    data["diagnostics_updated_at"] = timezone.now().isoformat()
    cache.set(
        MQTT_BRIDGE_DIAGNOSTICS_CACHE_KEY,
        data,
        MQTT_BRIDGE_DIAGNOSTICS_CACHE_TIMEOUT,
    )
    try:
        from .models import MQTTBridgeStatus

        obj, _ = MQTTBridgeStatus.objects.get_or_create(
            key="default",
            defaults={"status": "disconnected"},
        )
        MQTTBridgeStatus.objects.filter(pk=obj.pk).update(bridge_diagnostics=data)
    except Exception:
        logger.debug("update_mqtt_bridge_diagnostics: DB write failed", exc_info=True)


def note_mqtt_bridge_diagnostics_error(message: str) -> None:
    if not message:
        return
    update_mqtt_bridge_diagnostics({"last_error": str(message)[:500]})


def get_mqtt_config(force_refresh: bool = False) -> Optional["MQTTConfiguration"]:
    """
    Get MQTT configuration from database with caching.

    Cache is automatically cleared when configuration is saved in Django admin.
    Use force_refresh=True when reconnecting so broker username/password and HMAC
    settings are always loaded from the database (avoids stale cache in the bridge process).

    Returns:
        MQTTConfiguration instance or None if not configured
    """
    from django.core.cache import cache

    if not force_refresh:
        cached = cache.get("mqtt_active_config")
        if cached is not None:
            if cached == "NO_CONFIG":
                logger.debug(
                    "get_mqtt_config force_refresh=False source=cache marker=NO_CONFIG"
                )
                return None
            logger.debug(
                "get_mqtt_config force_refresh=False source=cache snapshot=%s",
                mqtt_config_safe_snapshot(cached),
            )
            return cached

    # Force refresh or cache miss - query database
    try:
        from django.db import connection

        if "nemo_mqtt_mqttconfiguration" not in connection.introspection.table_names():
            logger.debug(
                "get_mqtt_config force_refresh=%s source=database table_missing",
                force_refresh,
            )
            return None

        from .models import MQTTConfiguration

        config = MQTTConfiguration.objects.filter(enabled=True).first()

        if config:
            cache.set("mqtt_active_config", config, 300)
        else:
            cache.set("mqtt_active_config", "NO_CONFIG", 300)

        logger.debug(
            "get_mqtt_config force_refresh=%s source=database snapshot=%s",
            force_refresh,
            mqtt_config_safe_snapshot(config),
        )
        return config
    except Exception as e:
        logger.warning(f"Could not load MQTT configuration from database: {e}")
        return None


def format_topic(
    topic_prefix: str, event_type: str, resource_id: Optional[str] = None
) -> str:
    """
    Format MQTT topic based on event type and resource ID.

    Args:
        topic_prefix: Base topic prefix
        event_type: Type of event (e.g., 'tool_save', 'reservation_created')
        resource_id: Optional resource ID to include in topic

    Returns:
        Formatted MQTT topic string
    """
    topic_parts = [topic_prefix, event_type]
    if resource_id:
        topic_parts.append(str(resource_id))

    return "/".join(topic_parts)


def serialize_model_instance(instance, fields: Optional[list] = None) -> Dict[str, Any]:
    """
    Serialize a Django model instance to a dictionary.

    Args:
        instance: Django model instance
        fields: Optional list of fields to include (if None, includes all fields)

    Returns:
        Dictionary representation of the model instance
    """
    if fields is None:
        fields = [field.name for field in instance._meta.fields]

    data = {}
    for field_name in fields:
        if hasattr(instance, field_name):
            value = getattr(instance, field_name)
            if hasattr(value, "isoformat"):  # Handle datetime fields
                data[field_name] = value.isoformat()
            elif hasattr(value, "id"):  # Handle foreign key fields
                data[field_name] = value.id
            else:
                data[field_name] = value

    return data


def log_mqtt_message(
    topic: str,
    payload: str,
    qos: int = 0,
    retained: bool = False,
    success: bool = True,
    error_message: str = None,
):
    """
    Log MQTT message to database for debugging and monitoring.

    Args:
        topic: MQTT topic
        payload: Message payload
        qos: Quality of Service level
        retained: Whether message was retained
        success: Whether message was sent successfully
        error_message: Error message if sending failed
    """
    try:
        from .models import MQTTMessageLog

        MQTTMessageLog.objects.create(
            topic=topic,
            payload=payload,
            qos=qos,
            retained=retained,
            success=success,
            error_message=error_message,
        )
    except Exception as e:
        logger.error(f"Failed to log MQTT message: {e}")


def sign_payload_hmac(payload: str, secret_key: str, algorithm: str = "sha256") -> str:
    """
    Sign a payload with HMAC-SHA256 and return a JSON envelope with payload, hmac, and algo.
    Subscribers can verify authenticity and integrity using the same shared secret.

    The algorithm parameter is ignored; only SHA-256 is used. It is kept for API compatibility.

    Args:
        payload: Raw message payload (string)
        secret_key: Shared secret for HMAC
        algorithm: Ignored; always SHA-256 (kept for compatibility)

    Returns:
        JSON string: {"payload": "<original>", "hmac": "<hex>", "algo": "sha256"}
    """
    import hmac as hm
    import hashlib

    key = secret_key.encode("utf-8") if isinstance(secret_key, str) else secret_key
    msg = payload.encode("utf-8") if isinstance(payload, str) else payload
    sig = hm.new(key, msg, hashlib.sha256).hexdigest()
    return json.dumps({"payload": payload, "hmac": sig, "algo": "sha256"})


def verify_payload_hmac(envelope_json: str, secret_key: str) -> tuple:
    """
    Verify an HMAC-signed envelope (SHA-256 only) and return (valid, original_payload).

    Only SHA-256 is supported. Envelopes signed with other algorithms will fail verification.

    Args:
        envelope_json: JSON string from sign_payload_hmac
        secret_key: Same shared secret used to sign

    Returns:
        (True, payload_string) if valid, (False, "") otherwise
    """
    import hmac as hm
    import hashlib

    try:
        data = json.loads(envelope_json)
        payload = data.get("payload")
        sig = data.get("hmac")
        algo = (data.get("algo") or "sha256").lower()
        if payload is None or sig is None:
            return False, ""
        if algo != "sha256":
            return False, ""
        key = secret_key.encode("utf-8") if isinstance(secret_key, str) else secret_key
        msg = payload.encode("utf-8") if isinstance(payload, str) else payload
        expected = hm.new(key, msg, hashlib.sha256).hexdigest()
        if not hm.compare_digest(expected, sig):
            return False, ""
        return True, payload
    except (json.JSONDecodeError, TypeError, AttributeError):
        return False, ""


def render_combine_responses(*responses) -> HttpResponse:
    """
    Combine multiple HttpResponse objects into a single response.

    This function is required by NEMO's plugin system.

    Args:
        *responses: Variable number of HttpResponse objects

    Returns:
        Combined HttpResponse
    """
    if not responses:
        return HttpResponse()

    if len(responses) == 1:
        return responses[0]

    # Combine content from all responses
    combined_content = b"".join(
        response.content for response in responses if response.content
    )

    # Use the first response as the base and update its content
    combined_response = HttpResponse(combined_content)
    combined_response.status_code = responses[0].status_code

    # Copy headers from all responses
    for response in responses:
        for header, value in response.items():
            combined_response[header] = value

    return combined_response
