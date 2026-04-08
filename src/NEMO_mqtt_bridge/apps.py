import atexit
import logging
import os
import threading
import time

from django.apps import AppConfig

logger = logging.getLogger(__name__)

_bridge_atexit_registered = False


def should_run_bridge_in_django() -> bool:
    """
    When False, Django does not spawn the bridge thread; run
    python -m NEMO_mqtt_bridge.postgres_mqtt_bridge (or systemd) separately.
    Env NEMO_MQTT_BRIDGE_RUN_IN_DJANGO=0 or Django setting NEMO_MQTT_BRIDGE_RUN_IN_DJANGO = False.
    Default True for backward compatibility.
    """
    env_val = os.environ.get("NEMO_MQTT_BRIDGE_RUN_IN_DJANGO", "").strip().lower()
    if env_val in ("0", "false", "no", "off"):
        return False
    try:
        from django.conf import settings

        if hasattr(settings, "NEMO_MQTT_BRIDGE_RUN_IN_DJANGO"):
            return bool(settings.NEMO_MQTT_BRIDGE_RUN_IN_DJANGO)
    except Exception:
        pass
    return True


def _atexit_stop_mqtt_bridge():
    try:
        from .postgres_mqtt_bridge import get_mqtt_bridge

        bridge = get_mqtt_bridge()
        if bridge.running:
            bridge.stop()
    except Exception:
        pass


class MqttPluginConfig(AppConfig):
    name = "NEMO_mqtt_bridge"
    label = "NEMO_mqtt_bridge"
    verbose_name = "MQTT Plugin"
    default_auto_field = "django.db.models.AutoField"
    _initialized = False
    _auto_service_started = False

    def ready(self):
        """
        Initialize the MQTT plugin when Django starts.
        This sets up signal handlers and starts the PostgreSQL-MQTT Bridge service.
        """
        # Prevent multiple initializations during development auto-reload
        if self._initialized:
            logger.info("MQTT plugin already initialized, skipping...")
            return

        if self.get_migration_args():
            logger.info("Migration detected, skipping MQTT plugin initialization")
            return

        # Check for NEMO dependencies (like nemo-publications plugin)
        try:
            from NEMO.plugins.utils import check_extra_dependencies

            check_extra_dependencies(self.name, ["NEMO", "NEMO-CE"])
        except ImportError:
            # NEMO.plugins.utils might not be available in all versions
            pass

        # Import signal handlers to register them immediately
        try:
            from . import signals
        except Exception as e:
            logger.warning(f"Failed to import signals: {e}")

        # Import customization to register it immediately
        try:
            from . import customization
        except Exception as e:
            logger.warning(f"Failed to import customization: {e}")

        # Mark as initialized to prevent multiple calls
        self._initialized = True
        logger.info("MQTT plugin initialization started")

        # Initialize DB publisher for MQTT events; start bridge when configured to run in-process
        try:
            from .utils import get_mqtt_config

            config = get_mqtt_config()
            logger.info("MQTT config result: %s", config)
            if config and config.enabled:
                logger.info(
                    "MQTT plugin initialized with enabled config: %s",
                    config.name,
                )
                logger.info("MQTT events will be published via PostgreSQL to MQTT broker")
            else:
                logger.info(
                    "MQTT plugin loaded without enabled configuration; "
                    "bridge will idle until MQTT is enabled in customization"
                )

            if should_run_bridge_in_django():
                self._start_external_mqtt_service()
            else:
                logger.info(
                    "NEMO_MQTT_BRIDGE_RUN_IN_DJANGO is disabled; start the bridge separately "
                    "(e.g. python -m NEMO_mqtt_bridge.postgres_mqtt_bridge)"
                )

        except Exception as e:
            logger.error("Failed to initialize MQTT plugin: %s", e)

        logger.info(
            "MQTT plugin: Signal handlers and customization registered. Events will be published via PostgreSQL."
        )

    def _start_external_mqtt_service(self):
        """Start the PostgreSQL-MQTT Bridge service in a daemon thread."""
        global _bridge_atexit_registered
        if self._auto_service_started:
            logger.info("PostgreSQL-MQTT Bridge already started, skipping...")
            return

        try:
            logger.info("Starting PostgreSQL-MQTT Bridge service in-process...")

            from .postgres_mqtt_bridge import get_mqtt_bridge

            mqtt_bridge = get_mqtt_bridge()

            def run_bridge_service():
                try:
                    mqtt_bridge.start()
                    while mqtt_bridge.running:
                        time.sleep(1)
                except Exception as e:
                    logger.error("PostgreSQL-MQTT Bridge error: %s", e)

            mqtt_thread = threading.Thread(target=run_bridge_service, daemon=True)
            mqtt_thread.start()

            self._auto_service_started = True
            if not _bridge_atexit_registered:
                atexit.register(_atexit_stop_mqtt_bridge)
                _bridge_atexit_registered = True
            logger.info("PostgreSQL-MQTT Bridge thread started")

        except Exception as e:
            logger.error("Failed to start PostgreSQL-MQTT Bridge: %s", e)
            logger.info(
                "MQTT events will still be enqueued, but the bridge process/thread is not running"
            )

    def get_migration_args(self):
        """Get migration-related command line arguments (migrate, makemigrations, showmigrations, etc.)"""
        import sys

        return [
            arg
            for arg in sys.argv
            if "migrate" in arg or "makemigrations" in arg or "showmigrations" in arg
        ]

    def disconnect_mqtt(self):
        """Stop the in-process bridge (releases lock, disconnects MQTT and PostgreSQL)."""
        try:
            from .postgres_mqtt_bridge import get_mqtt_bridge

            bridge = get_mqtt_bridge()
            if bridge.running:
                bridge.stop()
                logger.info("PostgreSQL-MQTT Bridge stopped")
        except Exception as e:
            logger.debug("disconnect_mqtt: %s", e)
