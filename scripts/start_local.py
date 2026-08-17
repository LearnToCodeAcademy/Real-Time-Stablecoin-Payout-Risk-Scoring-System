"""Start the FastAPI service and React console for local operations."""

from __future__ import annotations

import os
import shutil
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _command(name: str) -> str:
    resolved = shutil.which(name)
    if not resolved:
        raise SystemExit(f"Required command is not installed or not on PATH: {name}")
    return resolved


def _port_available(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        return probe.connect_ex(("127.0.0.1", port)) != 0


def _stop_process_tree(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    else:
        process.send_signal(signal.SIGINT)


def main() -> int:
    occupied = [str(port) for port in (8000, 5173) if not _port_available(port)]
    if occupied:
        raise SystemExit(f"Required local port(s) already in use: {', '.join(occupied)}")
    python = (
        str(ROOT / ".venv" / "Scripts" / "python.exe")
        if os.name == "nt"
        else str(ROOT / ".venv" / "bin" / "python")
    )
    if not Path(python).exists():
        python = sys.executable
    npm = _command("npm.cmd" if os.name == "nt" else "npm")
    environment = os.environ.copy()
    environment.setdefault("ENABLE_LOCAL_TRAINING", "true")
    environment.setdefault("CORS_ORIGINS", "http://127.0.0.1:5173,http://localhost:5173")

    api = subprocess.Popen(
        [python, "-m", "uvicorn", "api:app", "--host", "127.0.0.1", "--port", "8000"],
        cwd=ROOT,
        env=environment,
    )
    console = subprocess.Popen(
        [npm, "run", "dev", "--", "--port", "5173"],
        cwd=ROOT / "frontend",
        env=environment,
    )
    children = [api, console]
    print("\nStablecoin Risk System is starting:")
    print("  Checker:  http://127.0.0.1:5173/")
    print("  Training: http://127.0.0.1:5173/training.html")
    print("  API docs: http://127.0.0.1:8000/docs")
    print("\nPress Ctrl+C to stop both services.\n")
    try:
        while all(process.poll() is None for process in children):
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        for process in children:
            _stop_process_tree(process)
        for process in children:
            try:
                process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                process.terminate()
    return next((process.returncode or 1 for process in children if process.returncode), 0)


if __name__ == "__main__":
    raise SystemExit(main())
