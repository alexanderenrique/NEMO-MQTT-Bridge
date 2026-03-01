"""
Utility functions for MQTT plugin.
"""

import json
import logging
from typing import Dict, Any, Optional, TYPE_CHECKING
from django.conf import settings
from django.utils import timezone
from django.http import HttpResponse

if TYPE_CHECKING:
    from .models import MQTTConfiguration

logger = logging.getLogger(__name__)


def get_mqtt_config(force_refresh: bool = False) -> Optional[MQTTConfiguration]:
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
        config = cache.get("mqtt_active_config")
        if config is not None:
            return config if config != "NO_CONFIG" else None

    # Force refresh or cache miss - query database
    try:
        from .models import MQTTConfiguration

        config = MQTTConfiguration.objects.filter(enabled=True).first()

        if config:
            cache.set("mqtt_active_config", config, 300)
        else:
            cache.set("mqtt_active_config", "NO_CONFIG", 300)

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


def is_event_enabled(event_type: str) -> bool:
    """
    Check if a specific event type is enabled for MQTT publishing.

    Args:
        event_type: Type of event to check

    Returns:
        True if event is enabled, False otherwise
    """
    try:
        from .models import MQTTEventFilter

        filter_obj = MQTTEventFilter.objects.filter(event_type=event_type).first()
        if filter_obj:
            return filter_obj.enabled

        # Default to enabled if no filter exists
        return True
    except Exception as e:
        logger.warning(f"Could not check event filter for {event_type}: {e}")
        return True


def get_event_topic_override(event_type: str) -> Optional[str]:
    """
    Get custom topic override for an event type.

    Args:
        event_type: Type of event

    Returns:
        Custom topic string if configured, None otherwise
    """
    try:
        from .models import MQTTEventFilter

        filter_obj = MQTTEventFilter.objects.filter(event_type=event_type).first()
        if filter_obj and filter_obj.topic_override:
            return filter_obj.topic_override

        return None
    except Exception as e:
        logger.warning(f"Could not get topic override for {event_type}: {e}")
        return None


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
