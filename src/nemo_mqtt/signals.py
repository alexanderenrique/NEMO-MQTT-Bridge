"""
Django signal handlers for MQTT plugin.
These signals will trigger MQTT message publishing when NEMO events occur.
"""

import json
import logging
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.conf import settings
from django.core.cache import cache

from .models import MQTTConfiguration


# Check if NEMO is available
def _check_nemo_availability():
    """Check if NEMO is available and return the models if so"""
    try:
        from NEMO.models import (
            Tool,
            Area,
            User,
            Reservation,
            UsageEvent,
            AreaAccessRecord,
        )

        return True, Tool, Area, User, Reservation, UsageEvent, AreaAccessRecord
    except (ImportError, RuntimeError):
        return False, None, None, None, None, None, None


NEMO_AVAILABLE, Tool, Area, User, Reservation, UsageEvent, AreaAccessRecord = (
    _check_nemo_availability()
)

logger = logging.getLogger(__name__)


class MQTTSignalHandler:
    """Handles MQTT signal processing and message publishing via Redis"""

    def __init__(self):
        self.redis_publisher = None
        self._initialize_redis_publisher()

    def _initialize_redis_publisher(self):
        """Initialize Redis publisher for MQTT events"""
        try:
            from .redis_publisher import redis_publisher

            self.redis_publisher = redis_publisher
            logger.info("Redis MQTT publisher initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Redis publisher: {e}")
            self.redis_publisher = None

    def _get_mqtt_config(self):
        """Get MQTT configuration from database"""
        try:
            config = MQTTConfiguration.objects.filter(enabled=True).first()
            if config:
                return config
            else:
                # Return default config if none found
                return MQTTConfiguration(
                    qos_level=1,  # Default to QoS 1 for reliability
                    retain_messages=False,
                )
        except Exception as e:
            logger.warning(f"Failed to get MQTT configuration: {e}")
            # Return default config on error
            return MQTTConfiguration(
                qos_level=1, retain_messages=False  # Default to QoS 1 for reliability
            )

    def publish_message(self, topic, data):
        """Publish a message via Redis to external MQTT service"""
        import uuid

        signal_id = str(uuid.uuid4())[:8]

        print(f"\n[SIGNAL-{signal_id}] Django Signal → Redis Publisher")
        print(f"   Topic: {topic}")
        print(f"   Data: {json.dumps(data, indent=2)}")

        if self.redis_publisher:
            try:
                # Get MQTT configuration for QoS and retain settings
                config = self._get_mqtt_config()

                success = self.redis_publisher.publish_event(
                    topic,
                    json.dumps(data),
                    qos=config.qos_level,
                    retain=config.retain_messages,
                )
                if success:
                    print(f"[OK] [SIGNAL-{signal_id}] Successfully published to Redis")
                    print(f"   Message sent to Redis list 'nemo_mqtt_events'")
                    logger.info(f"Successfully published to Redis: {topic}")
                else:
                    print(f"[ERROR] [SIGNAL-{signal_id}] Failed to publish to Redis")
                    logger.error(f"Failed to publish to Redis: {topic}")
            except Exception as e:
                print(
                    f"[ERROR] [SIGNAL-{signal_id}] Exception publishing to Redis: {e}"
                )
                logger.error(f"Failed to publish MQTT message via Redis: {e}")
        else:
            print(f"[ERROR] [SIGNAL-{signal_id}] Redis publisher not available")
            logger.warning("Redis publisher not available")


# Global signal handler instance
print("Initializing MQTT Signal Handler...")
signal_handler = MQTTSignalHandler()
print(f"MQTT Signal Handler initialized: {id(signal_handler)}")


# Only register signal handlers if NEMO is available
if NEMO_AVAILABLE:
    # Tool-related signals
    @receiver(post_save, sender=Tool)
    def tool_saved(sender, instance, created, **kwargs):
        """Signal handler for tool save events"""
        import uuid

        signal_id = str(uuid.uuid4())[:8]
        print(f"\n[TOOL-SIGNAL-{signal_id}] Tool save event triggered")
        print(f"   Tool: {instance.name} (ID: {instance.id})")
        print(f"   Created: {created}")
        print(f"   Operational: {instance.operational}")

        if signal_handler.redis_publisher:
            action = "created" if created else "updated"
            data = {
                "event": f"tool_{action}",
                "tool_id": instance.id,
                "tool_name": instance.name,
                "tool_status": instance.operational,
                "timestamp": instance._state.adding,
            }
            print(f"[TOOL-SIGNAL-{signal_id}] Publishing tool_{action} event...")
            signal_handler.publish_message(f"nemo/tools/{instance.id}", data)
        else:
            print(f"[ERROR] [TOOL-SIGNAL-{signal_id}] Redis publisher not available")

    @receiver(post_save, sender=Area)
    def area_saved(sender, instance, created, **kwargs):
        """Signal handler for area save events"""
        if signal_handler.redis_publisher:
            action = "created" if created else "updated"
            data = {
                "event": f"area_{action}",
                "area_id": instance.id,
                "area_name": instance.name,
                "area_requires_reservation": instance.requires_reservation,
                "timestamp": instance._state.adding,
            }
            signal_handler.publish_message(f"nemo/areas/{instance.id}", data)

    # Reservation-related signals
    @receiver(post_save, sender=Reservation)
    def reservation_saved(sender, instance, created, **kwargs):
        """Signal handler for reservation save events"""
        if signal_handler.redis_publisher:
            action = "created" if created else "updated"
            data = {
                "event": f"reservation_{action}",
                "reservation_id": instance.id,
                "user_id": instance.user.id,
                "user_name": instance.user.get_full_name(),
                "start_time": instance.start.isoformat() if instance.start else None,
                "end_time": instance.end.isoformat() if instance.end else None,
                "timestamp": instance._state.adding,
            }
            signal_handler.publish_message(f"nemo/reservations/{instance.id}", data)

    # Usage event signals — SINGLE SOURCE OF TRUTH for tool enable/disable
    # NEMO (and nemo-ce) does not emit tool_enabled/tool_disabled signals; enable = new UsageEvent
    # (no end), disable = UsageEvent.save() with end set. This handler publishes to Redis for both.
    @receiver(post_save, sender=UsageEvent)
    def usage_event_saved(sender, instance, created, **kwargs):
        """Publish tool usage start/end to Redis. This is the only source for tool enable/disable."""
        import uuid

        signal_id = str(uuid.uuid4())[:8]

        if not signal_handler.redis_publisher:
            print(f"[SIGNAL-{signal_id}] Redis publisher not available")
            return

        # End time set = tool disabled (usage ended); no end = tool enabled (usage started)
        if instance.end is not None:
            # Tool disabled / usage ended — publish only .../disabled (no .../end to avoid duplicate/conflicting status)
            disabled_data = {
                "event": "tool_disabled",
                "tool_id": instance.tool.id,
                "tool_name": instance.tool.name,
                "usage_id": instance.id,
                "user_name": instance.user.get_full_name(),
                "end_time": instance.end.isoformat() if instance.end else None,
            }
            signal_handler.publish_message(
                f"nemo/tools/{instance.tool.id}/disabled", disabled_data
            )
            print(f"[SIGNAL-{signal_id}] disabled event published to Redis")
        else:
            # Tool enabled / usage started — publish only .../enabled (no .../start to avoid duplicate status)
            print(f"[SIGNAL-{signal_id}] No end time - Publishing tool_enabled")

            enabled_data = {
                "event": "tool_enabled",
                "tool_id": instance.tool.id,
                "tool_name": instance.tool.name,
                "usage_id": instance.id,
                "user_name": instance.user.get_full_name(),
                "start_time": instance.start.isoformat() if instance.start else None,
            }
            signal_handler.publish_message(
                f"nemo/tools/{instance.tool.id}/enabled", enabled_data
            )
            print(f"[SIGNAL-{signal_id}] enabled event published to Redis")

        print(f"[SIGNAL-{signal_id}] Signal processing complete")
        logger.info(f"Published events for UsageEvent {instance.id}")

    # Area access signals
    @receiver(post_save, sender=AreaAccessRecord)
    def area_access_saved(sender, instance, created, **kwargs):
        """Signal handler for area access save events"""
        if signal_handler.redis_publisher and created:
            data = {
                "event": "area_access",
                "access_id": instance.id,
                "user_id": instance.customer.id,
                "user_name": instance.customer.get_full_name(),
                "area_id": instance.area.id,
                "area_name": instance.area.name,
                "access_time": instance.start.isoformat() if instance.start else None,
                "timestamp": instance._state.adding,
            }
            signal_handler.publish_message(f"nemo/area_access/{instance.id}", data)
