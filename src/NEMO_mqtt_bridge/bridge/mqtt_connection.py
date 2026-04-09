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

    broker_host = config.broker_host or "localhost"
    broker_port = config.broker_port or 1883
    keepalive = config.keepalive or 60

    logger.debug(
        "MQTT connect: client_id=%s %s:%s keepalive=%s username=%r password_set=%s",
        client_id,
        broker_host,
        broker_port,
        keepalive,
        config.username or None,
        use_auth,
    )

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
    logger.info(
        "MQTT connection timeout to %s:%s after %ss",
        broker_host,
        broker_port,
        timeout,
    )
    raise RuntimeError(
        f"Connection timeout to {broker_host}:{broker_port} after {timeout}s"
    )
