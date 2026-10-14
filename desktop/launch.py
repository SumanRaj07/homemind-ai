"""HomeMind AI desktop launcher (Windows-friendly, works anywhere).

This is the desktop application entry point. It owns the backend process
lifecycle:

1. Acquires a lock file so two launchers never start two backends.
2. Reuses an already-running healthy backend instead of duplicating it.
3. Starts the FastAPI backend (loopback only) when needed and waits for
   ``/health``.
4. Reports model availability clearly (Ollama down -> actionable message,
   never a cloud fallback).
5. Opens the UI in a desktop window (pywebview when installed, otherwise the
   default browser).
6. On exit, stops *only* the backend it started and releases the lock.

The browser UI and this desktop launcher share the exact same backend, the
same SQLite database and the same Streamlit frontend code — there is no
second copy of the AI engine or storage.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import webbrowser
from dataclasses import dataclass
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent


@dataclass
class LauncherConfig:
    backend_port: int = int(os.environ.get("HOMEMIND_PORT", "8000"))
    ui_port: int = int(os.environ.get("HOMEMIND_UI_PORT", "8501"))
    data_dir: Path = Path(
        os.environ.get("HOMEMIND_DATA_DIR", str(Path.home() / ".homemind"))
    )

    @property
    def api_url(self) -> str:
        return f"http://127.0.0.1:{self.backend_port}"

    @property
    def ui_url(self) -> str:
        return f"http://127.0.0.1:{self.ui_port}"

    @property
    def lock_path(self) -> Path:
        return self.data_dir / "backend.lock"


def _http_get(url: str, timeout: float = 2.0):
    """Loopback HTTP GET that ignores proxy env vars (local-first)."""
    return httpx.get(url, timeout=timeout, trust_env=False)


def is_process_alive(pid: int) -> bool:
    """True if a process with this PID exists (any OS)."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # exists, but owned by someone else
    except OSError:
        return False
    return True


def backend_is_healthy(api_url: str) -> bool:
    try:
        resp = _http_get(f"{api_url}/health", timeout=2.0)
        return resp.status_code == 200
    except (httpx.ConnectError, httpx.TimeoutException, OSError):
        return False


def read_lock(lock_path: Path) -> dict | None:
    try:
        return json.loads(lock_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def acquire_lock(cfg: LauncherConfig) -> tuple[bool, dict | None]:
    """Acquire the backend lock.

    Returns (owns_lock, existing_info). If another live backend already holds
    the lock, we do NOT start a duplicate — the caller should reuse it.
    A stale lock (dead PID or unhealthy backend) is taken over.
    """
    cfg.data_dir.mkdir(parents=True, exist_ok=True)
    existing = read_lock(cfg.lock_path)
    if existing:
        pid = int(existing.get("pid", 0) or 0)
        port = int(existing.get("port", 0) or 0)
        url = f"http://127.0.0.1:{port}" if port else cfg.api_url
        if pid and is_process_alive(pid) and backend_is_healthy(url):
            return False, existing
        # Stale lock — previous launcher died; safe to take over.
        try:
            cfg.lock_path.unlink()
        except OSError:
            pass
    info = {
        "pid": os.getpid(),
        "port": cfg.backend_port,
        "started_at": time.time(),
    }
    cfg.lock_path.write_text(json.dumps(info), encoding="utf-8")
    return True, info


def release_lock(cfg: LauncherConfig, owns: bool) -> None:
    if owns:
        try:
            cfg.lock_path.unlink()
        except OSError:
            pass


def start_backend(cfg: LauncherConfig) -> subprocess.Popen:
    """Start the FastAPI backend as a child process. Fixed argv — no user
    input is ever executed."""
    env = os.environ.copy()
    return subprocess.Popen(  # noqa: S603
        [sys.executable, "-m", "homemind.api.app"],
        cwd=str(ROOT / "src"),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
    )


def wait_for_backend(cfg: LauncherConfig, timeout_s: float = 60.0) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if backend_is_healthy(cfg.api_url):
            return True
        time.sleep(1.0)
    return False


def model_status(cfg: LauncherConfig) -> tuple[bool, str]:
    """Return (available, message) for the configured local model."""
    try:
        data = _http_get(f"{cfg.api_url}/status", timeout=10.0).json()
        return bool(data.get("model_available")), str(
            data.get("model_message", "")
        )
    except (httpx.ConnectError, httpx.TimeoutException, OSError, ValueError):
        return False, "Backend did not respond to /status."


def open_ui_window(cfg: LauncherConfig) -> bool:
    """Open the UI. Returns True if the call blocks until the window closes
    (pywebview), False if it returns immediately (browser fallback)."""
    try:
        import webview  # type: ignore[import-not-found]  # pywebview, optional

        webview.create_window("HomeMind AI", cfg.ui_url, width=1200, height=800)
        webview.start()
        return True
    except ImportError:
        print("pywebview not installed — opening in the default browser.", flush=True)
        webbrowser.open(cfg.ui_url)
        return False


def start_ui_process(cfg: LauncherConfig) -> subprocess.Popen:
    env = os.environ.copy()
    env["HOMEMIND_API_URL"] = cfg.api_url
    return subprocess.Popen(  # noqa: S603
        [
            sys.executable, "-m", "streamlit", "run",
            str(ROOT / "frontend" / "app.py"),
            "--server.port", str(cfg.ui_port),
            "--server.address", "127.0.0.1",
            "--browser.gatherUsageStats", "false",
        ],
        cwd=str(ROOT),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
    )


def stop_process(proc: subprocess.Popen, timeout_s: float = 10.0) -> None:
    """Terminate a process we own; escalate to kill if it won't stop."""
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=timeout_s)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5.0)


def main() -> int:
    cfg = LauncherConfig()
    owns_lock, existing = acquire_lock(cfg)

    backend_proc: subprocess.Popen | None = None
    if not owns_lock:
        print(
            f"Backend already running (PID {existing.get('pid') if existing else '?'}). "
            "Reusing it — no duplicate started.",
            flush=True,
        )
    else:
        print(
            f"Starting HomeMind AI backend (http://127.0.0.1:{cfg.backend_port})...",
            flush=True,
        )
        backend_proc = start_backend(cfg)
        if not wait_for_backend(cfg):
            print(
                "ERROR: backend did not become healthy within 60s. "
                f"Check that port {cfg.backend_port} is free and Python "
                "dependencies are installed.",
                file=sys.stderr,
            )
            stop_process(backend_proc)
            release_lock(cfg, owns_lock)
            return 1

    available, message = model_status(cfg)
    if available:
        print("Model ready.", flush=True)
    else:
        print(f"WARNING: {message}", flush=True)
        print(
            "The app will open, but chat needs a local model. "
            "Install Ollama (https://ollama.com), run `ollama serve`, "
            "then `ollama pull <model>`.",
            flush=True,
        )

    ui_proc = start_ui_process(cfg)
    print(f"HomeMind AI is running: {cfg.ui_url}", flush=True)
    try:
        if open_ui_window(cfg):
            print("UI window closed — shutting down.", flush=True)
        else:
            # Browser fallback doesn't block: stay alive until the user stops
            # us (Ctrl+C) or the UI process exits.
            print("Press Ctrl+C to stop.", flush=True)
            ui_proc.wait()
            print("UI process exited — shutting down.", flush=True)
        return 0
    except KeyboardInterrupt:
        print("\nShutting down...", flush=True)
        return 0
    finally:
        stop_process(ui_proc)
        # Only stop the backend if THIS launcher started it.
        if backend_proc is not None:
            stop_process(backend_proc)
        release_lock(cfg, owns_lock)


if __name__ == "__main__":
    raise SystemExit(main())
