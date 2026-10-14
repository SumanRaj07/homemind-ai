"""Unit tests: desktop launcher lifecycle (lock, reuse, shutdown)."""

from __future__ import annotations

import json
import os
import subprocess
import time

import pytest

from desktop import launch as launcher


@pytest.fixture
def cfg(tmp_path, monkeypatch):
    monkeypatch.setenv("HOMEMIND_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("HOMEMIND_PORT", "18923")  # unused port
    monkeypatch.setenv("HOMEMIND_UI_PORT", "18924")
    return launcher.LauncherConfig()


def test_acquire_lock_when_free(cfg):
    owns, info = launcher.acquire_lock(cfg)
    assert owns is True
    assert cfg.lock_path.exists()
    stored = json.loads(cfg.lock_path.read_text(encoding="utf-8"))
    assert stored["pid"] == os.getpid()
    assert stored["port"] == cfg.backend_port


def test_acquire_lock_reuses_live_backend(cfg, monkeypatch):
    """A second launcher must not start a duplicate backend."""
    cfg.lock_path.parent.mkdir(parents=True, exist_ok=True)
    cfg.lock_path.write_text(
        json.dumps({"pid": os.getpid(), "port": cfg.backend_port}), encoding="utf-8"
    )
    monkeypatch.setattr(launcher, "is_process_alive", lambda pid: True)
    monkeypatch.setattr(launcher, "backend_is_healthy", lambda url: True)
    owns, existing = launcher.acquire_lock(cfg)
    assert owns is False
    assert existing["pid"] == os.getpid()


def test_acquire_lock_takes_over_stale_lock(cfg, monkeypatch):
    cfg.lock_path.parent.mkdir(parents=True, exist_ok=True)
    cfg.lock_path.write_text(
        json.dumps({"pid": 99999999, "port": cfg.backend_port}), encoding="utf-8"
    )
    monkeypatch.setattr(launcher, "is_process_alive", lambda pid: False)
    owns, _ = launcher.acquire_lock(cfg)
    assert owns is True
    stored = json.loads(cfg.lock_path.read_text(encoding="utf-8"))
    assert stored["pid"] == os.getpid()


def test_release_lock_only_when_owned(cfg):
    owns, _ = launcher.acquire_lock(cfg)
    assert owns
    launcher.release_lock(cfg, owns=False)
    assert cfg.lock_path.exists()  # not ours to remove... (we own it, but flag says no)
    launcher.release_lock(cfg, owns=True)
    assert not cfg.lock_path.exists()


def test_wait_for_backend_timeout(cfg):
    # Nothing listens on this port: must return False, not hang.
    assert launcher.wait_for_backend(cfg, timeout_s=2.0) is False


def test_backend_is_healthy_false_on_closed_port(cfg):
    assert launcher.backend_is_healthy(cfg.api_url) is False


def test_model_status_unreachable(cfg):
    available, message = launcher.model_status(cfg)
    assert available is False
    assert message  # human-readable, non-empty


def test_stop_process_terminates_owned():
    proc = subprocess.Popen(["sleep", "60"])  # noqa: S603,S607
    try:
        assert proc.poll() is None
        launcher.stop_process(proc, timeout_s=5.0)
        assert proc.poll() is not None
    finally:
        if proc.poll() is None:
            proc.kill()


def test_stop_process_skips_already_dead():
    proc = subprocess.Popen(["true"])  # noqa: S603,S607
    proc.wait(timeout=5.0)
    launcher.stop_process(proc)  # must not raise


def test_is_process_alive_current_process():
    assert launcher.is_process_alive(os.getpid()) is True
    assert launcher.is_process_alive(99999999) is False


def test_lock_survives_reread(cfg):
    launcher.acquire_lock(cfg)
    assert launcher.read_lock(cfg.lock_path)["pid"] == os.getpid()
    launcher.release_lock(cfg, True)
    assert launcher.read_lock(cfg.lock_path) is None
    # Corrupt lock file reads as None (treated as free).
    cfg.data_dir.mkdir(parents=True, exist_ok=True)
    cfg.lock_path.write_text("not-json{{{", encoding="utf-8")
    assert launcher.read_lock(cfg.lock_path) is None
    time.sleep(0.01)
