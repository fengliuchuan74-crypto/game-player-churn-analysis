from __future__ import annotations

import os
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path

# Force packaged runs out of Streamlit's development mode before importing Streamlit.
os.environ["STREAMLIT_GLOBAL_DEVELOPMENT_MODE"] = "false"
os.environ["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"
os.environ["BROWSER"] = "none"

from streamlit.web import cli as stcli


def resource_path(name: str) -> Path:
    if getattr(sys, "_MEIPASS", None):
        return Path(sys._MEIPASS) / name
    return Path(__file__).resolve().parent / name


def find_free_port(start: int = 8501, attempts: int = 30) -> int:
    for port in range(start, start + attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError("No free localhost port available.")


def wait_for_server(port: int, timeout: float = 20.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.5)
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                return True
        time.sleep(0.3)
    return False


def open_browser_when_ready(port: int) -> None:
    url = f"http://127.0.0.1:{port}"
    if wait_for_server(port):
        webbrowser.open(url)
    else:
        print(f"Streamlit server did not start in time. Try opening {url} manually.", file=sys.stderr)


def launch_streamlit() -> int:
    app_file = resource_path("streamlit_app.py")
    if not app_file.exists():
        print(f"Missing app file: {app_file}", file=sys.stderr)
        return 1

    port = find_free_port()
    browser_thread = threading.Thread(
        target=open_browser_when_ready,
        args=(port,),
        daemon=True,
    )
    browser_thread.start()

    sys.argv = [
        "streamlit",
        "run",
        str(app_file),
        "--global.developmentMode",
        "false",
        "--server.headless",
        "true",
        "--server.address",
        "127.0.0.1",
        "--server.fileWatcherType",
        "none",
        "--browser.gatherUsageStats",
        "false",
        "--server.port",
        str(port),
    ]

    try:
        stcli.main()
        return 0
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 0


if __name__ == "__main__":
    raise SystemExit(launch_streamlit())
