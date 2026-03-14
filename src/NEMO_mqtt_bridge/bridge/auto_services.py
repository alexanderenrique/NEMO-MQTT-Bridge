"""
AUTO mode: start embedded MQTT broker for development/testing.

Uses mqttools (pure Python, no separate binary). PostgreSQL is used for the
event queue; no Redis needed.
"""

import logging
import subprocess
import time
from typing import Any, Optional

import paho.mqtt.client as mqtt

logger = logging.getLogger(__name__)


def cleanup_existing_services(redis_process=None):
    """Clean up any existing bridge instances.
    redis_process is ignored (kept for API compatibility)."""
    try:
        subprocess.run(["pkill", "-f", "postgres_mqtt_bridge"], capture_output=True)
        time.sleep(2)
        logger.info("Cleaned up existing services")
    except Exception as e:
        logger.warning("Cleanup warning: %s", e)


def start_mqtt_broker(config: Any) -> Optional[Any]:
    """
    Start embedded MQTT broker for AUTO mode.
    Returns broker controller or None if broker already running on port.
    """
    broker_port = config.broker_port if config else 1883

    # Check if broker already running
    try:
        tc = mqtt.Client(client_id="broker_check")
        tc.connect("localhost", broker_port, 5)
        tc.disconnect()
        logger.info("MQTT broker already running on port %s", broker_port)
        return None
    except Exception:
        pass

    try:
        from NEMO_mqtt_bridge.bridge.embedded_broker import EmbeddedBrokerController
    except ImportError:
        try:
            from NEMO.plugins.NEMO_mqtt_bridge.bridge.embedded_broker import (
                EmbeddedBrokerController,
            )
        except ImportError:
            raise RuntimeError(
                "Embedded broker requires mqttools. Install with: pip install mqttools"
            )

    controller = EmbeddedBrokerController(port=broker_port)
    controller.start()
    return controller


def start_mosquitto(config: Any) -> Optional[Any]:
    """Alias for start_mqtt_broker (backward compatibility)."""
    return start_mqtt_broker(config)
