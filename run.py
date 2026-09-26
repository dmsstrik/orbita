#!/usr/bin/env python3
"""Start a private local server, optionally opening its browser interface."""

from __future__ import annotations

import argparse
import errno
import json
import socket
import threading
import time
import urllib.request
import webbrowser


def open_when_ready(url: str):
    for _ in range(60):
        try:
            with urllib.request.urlopen(url + "/api/health", timeout=0.5) as response:
                if response.status == 200:
                    webbrowser.open(url)
                    return
        except OSError:
            time.sleep(0.2)


def main():
    parser = argparse.ArgumentParser(description="Орбита — анализ локальных социальных графов")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("Порт должен быть от 1024 до 65535.")
    try:
        with socket.socket() as check:
            check.bind(("127.0.0.1", args.port))
    except OSError as error:
        if error.errno == errno.EADDRINUSE:
            # Reopening the launcher should bring up an existing Orbita session.
            if not args.no_browser:
                try:
                    url = f"http://127.0.0.1:{args.port}"
                    with urllib.request.urlopen(url + "/api/health", timeout=1) as response:
                        info = json.load(response)
                    if isinstance(info, dict) and info.get("status") == "ok" and info.get("engine") == "nauty / pynauty":
                        webbrowser.open(url)
                        print(f"Орбита уже работает → {url}")
                        return
                except (OSError, ValueError):
                    pass
            parser.exit(1, f"Порт {args.port} занят. Возможно, Орбита уже открыта: http://127.0.0.1:{args.port}\nДля другого порта: python run.py --port 8788\n")
        parser.exit(1, f"Не удалось открыть локальный порт {args.port}: {error.strerror}. Запустите приложение из обычного терминала.\n")
    url = f"http://127.0.0.1:{args.port}"
    print(f"\nОрбита → {url}\nДля остановки нажмите Ctrl+C.\n", flush=True)
    if not args.no_browser:
        threading.Thread(target=open_when_ready, args=(url,), daemon=True).start()
    import uvicorn
    uvicorn.run("app.main:app", host=args.host, port=args.port, access_log=False, log_level="warning")


if __name__ == "__main__":
    main()
