"""
MQTT client connection setup (plain TCP; message authentication via HMAC on payloads).
"""

import logging
import os
import socket
import time
from typing import Any, Callable, Optional

import paho.mqtt.client as mqtt

logger = logging.getLogger(__name__)


def connect_mqtt(
    config,
    on_connect: Callable,
    on_disconnect: Callable,
    on_publish: Callable,
) -> mqtt.Client:
    """Create and connect MQTT client (plain TCP, no TLS)."""
    client_id = f"nemo_bridge_{socket.gethostname()}_{os.getpid()}"
    client = mqtt.Client(client_id=client_id)
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_publish = on_publish

    use_auth = bool(config.username and config.password)
    if use_auth:
        client.username_pw_set(config.username, config.password)
    logger.debug(
        "MQTT connect: %s:%s username=%r password_set=%s",
        config.broker_host or "localhost",
        config.broker_port or 1883,
        config.username or None,
        use_auth,
    )

    broker_host = config.broker_host or "localhost"
    broker_port = config.broker_port or 1883
    keepalive = config.keepalive or 60

    client.connect(broker_host, broker_port, keepalive)
    client.loop_start()

    timeout = 15
    for _ in range(int(timeout / 0.5)):
        if client.is_connected():
            return client
        time.sleep(0.5)

    try:
        client.loop_stop()
        client.disconnect()
    except Exception:
        pass
    raise RuntimeError(
        f"Connection timeout to {broker_host}:{broker_port} after {timeout}s"
    )
