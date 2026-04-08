"""
Process lock to prevent multiple PostgreSQL-MQTT bridge instances.
"""

import fcntl
import logging
import os
import tempfile

logger = logging.getLogger(__name__)

LOCK_PATH = os.path.join(tempfile.gettempdir(), "NEMO_mqtt_bridge.lock")


def _read_stored_pid():
    try:
        with open(LOCK_PATH, "r") as f:
            s = f.read().strip()
        return int(s) if s else None
    except (OSError, ValueError):
        return None


def read_bridge_lock_pid():
    """Return the PID stored in the bridge lock file, or None if missing/unreadable."""
    return _read_stored_pid()


def bridge_process_running():
    """True if the lock file lists a PID that is still alive (bridge likely running)."""
    pid = _read_stored_pid()
    return pid is not None and _pid_alive(pid)


def _pid_alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _remove_stale_lock_file():
    """Remove lock file if missing, empty, or recorded PID is not alive."""
    if not os.path.exists(LOCK_PATH):
        return
    pid = _read_stored_pid()
    if pid is None:
        try:
            os.remove(LOCK_PATH)
        except OSError:
            pass
        return
    if not _pid_alive(pid):
        try:
            os.remove(LOCK_PATH)
        except OSError:
            pass
        logger.info("Removed stale bridge lock (PID %s was dead)", pid)


def acquire_lock(fatal_if_locked=True):
    """
    Acquire an exclusive lock on LOCK_PATH.

    If another live instance holds the lock (or recorded PID is alive), ``fatal_if_locked``
    controls whether this process exits (standalone CLI) or returns None (embedded Django).
    """
    import sys

    for _ in range(3):
        lock_file = None
        try:
            lock_file = open(LOCK_PATH, "w")
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            if lock_file is not None:
                try:
                    lock_file.close()
                except OSError:
                    pass
            _remove_stale_lock_file()
            continue
        try:
            lock_file.write(str(os.getpid()))
            lock_file.flush()
            os.fsync(lock_file.fileno())
        except OSError:
            try:
                lock_file.close()
            except OSError:
                pass
            _remove_stale_lock_file()
            continue
        logger.info("Acquired bridge lock (PID: %s)", os.getpid())
        return lock_file

    holder = _read_stored_pid()
    if holder is not None and _pid_alive(holder):
        msg = "Another bridge instance is running (PID: %s)" % holder
        if fatal_if_locked:
            logger.warning("%s, exiting", msg)
            sys.exit(1)
        logger.warning(
            "%s; this worker will not run the in-process bridge",
            msg,
        )
        return None
    if fatal_if_locked:
        logger.warning(
            "Could not acquire bridge lock at %s (after stale cleanup), exiting",
            LOCK_PATH,
        )
        sys.exit(1)
    logger.warning(
        "Could not acquire bridge lock at %s; this worker will not run the in-process bridge",
        LOCK_PATH,
    )
    return None


def release_lock(lock_file):
    """Release the lock file."""
    if lock_file is None:
        return
    try:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        lock_file.close()
        if os.path.exists(LOCK_PATH):
            os.remove(LOCK_PATH)
        logger.info("Released bridge lock")
    except Exception as e:
        logger.error("Error releasing lock: %s", e)
