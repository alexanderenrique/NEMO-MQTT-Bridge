#!/usr/bin/env python3
"""
Supervise ``python -m NEMO_mqtt_bridge.postgres_mqtt_bridge`` as a subprocess.

Restarts the bridge when the child process exits, with exponential backoff.
Optionally treats a stale ``MQTTBridgeStatus.last_heartbeat`` as a wedged bridge
and SIGTERM/SIGKILLs the child (enable with ``--db-health`` or
``NEMO_MQTT_SUPERVISOR_DB_HEALTH=1``).

Only one supervisor per host should run (supervisor lock file). Do not run this
alongside a plain bridge service that starts the same module directly, or you
will fight for the bridge lock.
"""

from __future__ import annotations

import argparse
import fcntl
import logging
import os
import subprocess
import sys
import tempfile
import time

from NEMO_mqtt_bridge.envutil import env_truthy

logger = logging.getLogger(__name__)

SUPERVISOR_LOCK_PATH = os.path.join(
    tempfile.gettempdir(), "NEMO_mqtt_bridge.supervisor.lock"
)


def _supervisor_acquire_lock() -> object:
    """Exclusive lock so only one supervisor runs per machine."""
    try:
        lf = open(SUPERVISOR_LOCK_PATH, "w")
        fcntl.flock(lf.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        lf.write(str(os.getpid()))
        lf.flush()
        os.fsync(lf.fileno())
        logger.info("Supervisor lock acquired (PID %s)", os.getpid())
        return lf
    except OSError:
        logger.error(
            "Another bridge supervisor is already running (lock: %s); exiting",
            SUPERVISOR_LOCK_PATH,
        )
        sys.exit(1)


def _supervisor_release_lock(lock_file) -> None:
    if lock_file is None:
        return
    try:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        lock_file.close()
        if os.path.exists(SUPERVISOR_LOCK_PATH):
            os.remove(SUPERVISOR_LOCK_PATH)
        logger.info("Supervisor lock released")
    except OSError as e:
        logger.warning("Supervisor lock release: %s", e)


def _terminate_child(proc: subprocess.Popen, wait_sec: float) -> None:
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=wait_sec)
    except subprocess.TimeoutExpired:
        logger.error("Child did not exit after SIGTERM; sending SIGKILL")
        proc.kill()
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            logger.error("Child still running after SIGKILL")


def _heartbeat_stale(threshold_sec: float) -> bool:
    from django.utils import timezone

    from NEMO_mqtt_bridge.models import MQTTBridgeStatus

    row = MQTTBridgeStatus.objects.filter(key="default").first()
    if row is None or row.last_heartbeat is None:
        return False
    age = (timezone.now() - row.last_heartbeat).total_seconds()
    return age > threshold_sec


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [bridge_supervisor] %(message)s",
    )

    db_default = env_truthy("NEMO_MQTT_SUPERVISOR_DB_HEALTH")
    parser = argparse.ArgumentParser(
        description="Supervise the NEMO PostgreSQL–MQTT bridge subprocess",
    )
    parser.add_argument(
        "--auto",
        action="store_true",
        help="Pass --auto to the bridge (embedded broker / AUTO mode)",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=float(os.environ.get("NEMO_MQTT_SUPERVISOR_INTERVAL", "5")),
        help="Seconds between wait/health polls (default: 5 or env)",
    )
    parser.add_argument(
        "--backoff-initial",
        type=float,
        default=float(os.environ.get("NEMO_MQTT_SUPERVISOR_BACKOFF_INITIAL", "2")),
    )
    parser.add_argument(
        "--backoff-max",
        type=float,
        default=float(os.environ.get("NEMO_MQTT_SUPERVISOR_BACKOFF_MAX", "120")),
    )
    parser.add_argument(
        "--db-health",
        action="store_true",
        default=db_default,
        help="Use MQTTBridgeStatus.last_heartbeat to detect wedged bridge (default from NEMO_MQTT_SUPERVISOR_DB_HEALTH)",
    )
    parser.add_argument(
        "--no-db-health",
        action="store_false",
        dest="db_health",
        help="Disable DB heartbeat watchdog",
    )
    parser.add_argument(
        "--heartbeat-stale-sec",
        type=float,
        default=float(os.environ.get("NEMO_MQTT_SUPERVISOR_STALE_SEC", "90")),
        help="If last_heartbeat is older than this, restart child (with --db-health)",
    )
    parser.add_argument(
        "--startup-grace-sec",
        type=float,
        default=float(os.environ.get("NEMO_MQTT_SUPERVISOR_GRACE_SEC", "90")),
        help="Skip DB stale checks until this many seconds after each spawn",
    )
    parser.add_argument(
        "--terminate-wait-sec",
        type=float,
        default=float(os.environ.get("NEMO_MQTT_SUPERVISOR_TERM_WAIT", "30")),
    )
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])

    if args.db_health:
        if "DJANGO_SETTINGS_MODULE" not in os.environ:
            logger.warning(
                "DJANGO_SETTINGS_MODULE is not set; DB health checks need Django settings"
            )
        import django

        django.setup()

    lock_file = _supervisor_acquire_lock()
    shutdown = False
    child: subprocess.Popen | None = None

    def on_signal(signum, _frame):
        nonlocal shutdown
        logger.info("Received signal %s", signum)
        shutdown = True
        if child is not None and child.poll() is None:
            child.terminate()

    import signal

    signal.signal(signal.SIGTERM, on_signal)
    signal.signal(signal.SIGINT, on_signal)

    backoff = args.backoff_initial
    try:
        while not shutdown:
            cmd = [sys.executable, "-m", "NEMO_mqtt_bridge.postgres_mqtt_bridge"]
            if args.auto:
                cmd.append("--auto")
            logger.info("Spawning bridge: %s", " ".join(cmd))
            child = subprocess.Popen(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=None,
                stderr=None,
                start_new_session=True,
                close_fds=True,
            )
            backoff = args.backoff_initial
            grace_until = time.monotonic() + args.startup_grace_sec

            inner_break = False
            while not shutdown and not inner_break:
                try:
                    child.wait(timeout=args.interval)
                    rc = child.returncode
                    logger.warning("Bridge process exited with code %s", rc)
                    inner_break = True
                except subprocess.TimeoutExpired:
                    if args.db_health and time.monotonic() >= grace_until:
                        if _heartbeat_stale(args.heartbeat_stale_sec):
                            logger.error(
                                "Bridge DB heartbeat stale (>%ss since last_heartbeat); restarting child",
                                args.heartbeat_stale_sec,
                            )
                            _terminate_child(child, args.terminate_wait_sec)
                            inner_break = True

            if shutdown:
                if child is not None and child.poll() is None:
                    _terminate_child(child, args.terminate_wait_sec)
                break

            if not inner_break:
                continue

            logger.info("Restarting bridge after %ss backoff", backoff)
            time.sleep(backoff)
            backoff = min(backoff * 2, args.backoff_max)
    finally:
        _supervisor_release_lock(lock_file)


if __name__ == "__main__":
    main()
