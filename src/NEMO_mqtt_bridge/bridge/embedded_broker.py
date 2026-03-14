"""
Embedded MQTT broker using mqttools (pure Python, no separate binary).

Runs in a background thread. Used in AUTO mode when NEMO_MQTT_BRIDGE_AUTO_START
is enabled. mqttools implements MQTT 5.0; paho-mqtt (MQTT 3.1.1) clients
connect via protocol downgrade.
"""

import logging
import time
from typing import Any, Optional

import paho.mqtt.client as mqtt

logger = logging.getLogger(__name__)


class EmbeddedBrokerController:
    """
    Runs mqttools broker in a background thread.
    Call start() to begin, shutdown() to stop.
    """

    def __init__(self, port: int = 1883):
        self.port = port
        self._broker: Any = None
        self._started = False

    def start(self) -> None:
        """Start the broker in a background thread and wait until it accepts connections."""
        if self._started:
            return

        try:
            from mqttools import BrokerThread
        except ImportError:
            raise RuntimeError(
                "mqttools is required for embedded broker. Install with: pip install mqttools"
            )

        self._broker = BrokerThread(("127.0.0.1", self.port))
        self._broker.start()
        self._started = True

        # Wait for broker to accept connections
        for i in range(20):
            try:
                client = mqtt.Client(client_id=f"embedded_check_{i}")
                client.connect("127.0.0.1", self.port, 5)
                client.disconnect()
                logger.info("Embedded MQTT broker started on port %s", self.port)
                return
            except Exception:
                time.sleep(1)

        self._broker.stop()
        self._started = False
        raise RuntimeError(
            "Embedded MQTT broker failed to accept connections within 20 seconds"
        )

    def shutdown(self) -> None:
        """Stop the broker."""
        if self._broker and self._started:
            try:
                self._broker.stop()
            except Exception as e:
                logger.debug("Broker stop: %s", e)
        self._started = False
        self._broker = None
        logger.info("Embedded MQTT broker stopped")
