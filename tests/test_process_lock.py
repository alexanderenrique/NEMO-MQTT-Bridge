"""Tests for bridge process lock (singleton / Gunicorn-safe embedded mode)."""

import builtins
import errno
import os
from unittest.mock import MagicMock

import pytest

from NEMO_mqtt_bridge.bridge import process_lock as pl


def test_acquire_lock_nonfatal_returns_none_when_holder_alive(tmp_path, monkeypatch):
    lock_path = tmp_path / "nemo.lock"
    lock_path.write_text("424242\n", encoding="ascii")
    monkeypatch.setattr(pl, "LOCK_PATH", str(lock_path))

    def flock_fail(fd, op):
        raise OSError(errno.EAGAIN, "would block")

    monkeypatch.setattr(pl.fcntl, "flock", flock_fail)
    monkeypatch.setattr(pl, "_remove_stale_lock_file", lambda: None)

    def alive(pid):
        return pid == 424242

    monkeypatch.setattr(pl, "_pid_alive", alive)
    assert pl.acquire_lock(fatal_if_locked=False) is None


def test_acquire_lock_fatal_exits_when_holder_alive(tmp_path, monkeypatch):
    lock_path = tmp_path / "nemo.lock"
    lock_path.write_text("424242\n", encoding="ascii")
    monkeypatch.setattr(pl, "LOCK_PATH", str(lock_path))

    def flock_fail(fd, op):
        raise OSError(errno.EAGAIN, "would block")

    monkeypatch.setattr(pl.fcntl, "flock", flock_fail)
    monkeypatch.setattr(pl, "_remove_stale_lock_file", lambda: None)
    monkeypatch.setattr(pl, "_pid_alive", lambda pid: pid == 424242)

    with pytest.raises(SystemExit) as exc:
        pl.acquire_lock(fatal_if_locked=True)
    assert exc.value.code == 1


def test_acquire_lock_retry_succeeds_after_first_flock_fails(tmp_path, monkeypatch):
    lock_path = str(tmp_path / "bridge.lock")
    monkeypatch.setattr(pl, "LOCK_PATH", lock_path)

    mock_file = MagicMock()
    mock_file.fileno.return_value = 7

    n = {"flock": 0, "opens": 0}
    real_open = builtins.open

    def fake_open(path, mode="r", *a, **kw):
        if os.fspath(path) == lock_path and "w" in mode:
            n["opens"] += 1
            return mock_file
        return real_open(path, mode, *a, **kw)

    def flock_side_effect(fd, op):
        n["flock"] += 1
        if n["flock"] == 1:
            raise OSError(errno.EAGAIN, "would block")
        return None

    monkeypatch.setattr(pl.fcntl, "flock", flock_side_effect)
    monkeypatch.setattr(builtins, "open", fake_open)
    monkeypatch.setattr(pl.os, "fsync", lambda _fd: None)

    result = pl.acquire_lock(fatal_if_locked=True)
    assert result is mock_file
    mock_file.write.assert_called_once()
    mock_file.flush.assert_called_once()


def test_acquire_release_roundtrip_real_lock(tmp_path, monkeypatch):
    monkeypatch.setattr(pl, "LOCK_PATH", str(tmp_path / "real.lock"))
    handle = pl.acquire_lock(fatal_if_locked=True)
    assert handle is not None
    pl.release_lock(handle)
    handle2 = pl.acquire_lock(fatal_if_locked=True)
    assert handle2 is not None
    pl.release_lock(handle2)
