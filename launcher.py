"""Local, dependency-free launcher for the OSM browser game (Python 3.10+)."""

from __future__ import annotations

import argparse
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import shutil
import socket
import sys
from urllib.parse import unquote, urlsplit
import webbrowser


# Explicit paths: the server must never expose other workspace files.
STATIC_FILES = (
    "index.html",
    "styles.css",
    "bootstrap.js",
    "music.js",
    "assets/music-theme.mp3",
    "game.py",
    "engine.py",
    "content.py",
    "scene.svg",
    "manifest.webmanifest",
    "sw.js",
    "assets/icon.svg",
    "assets/icon-192.png",
    "assets/icon-512.png",
    "vendor/brython.min.js",
    "vendor/LICENSE.txt",
)

MIME_TYPES = {
    ".mp3": "audio/mpeg",
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".py": "text/x-python; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".webmanifest": "application/manifest+json; charset=utf-8",
    ".txt": "text/plain; charset=utf-8",
}


def application_root() -> Path:
    """PyInstaller extracts bundled static files into _MEIPASS."""
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)).resolve()


def resolve_static_path(request_target: str, root: Path) -> Path | None:
    """Resolve only exact allowlisted files, including after URL decoding."""
    try:
        # Reject authority-style //host/path and absolute URI request targets.
        if not request_target.startswith("/") or request_target.startswith("//"):
            return None
        parsed = urlsplit(request_target)
        if parsed.scheme or parsed.netloc or parsed.fragment:
            return None
        path = unquote(parsed.path, encoding="utf-8", errors="strict")
    except (ValueError, UnicodeError):
        return None
    if "\\" in path or "\x00" in path:
        return None
    if path == "/":
        path = "/index.html"
    relative = path.removeprefix("/")
    if relative not in STATIC_FILES:
        return None
    base = root.resolve()
    candidate = (base / relative).resolve()
    try:
        candidate.relative_to(base)
    except ValueError:
        return None
    return candidate if candidate.is_file() else None


class GameRequestHandler(BaseHTTPRequestHandler):
    """GET/HEAD only; no directory listings or general-purpose file serving."""

    server_version = "OSMGame/1.0"
    sys_version = ""

    def __init__(self, *args, root: Path, **kwargs):
        self.root = root
        super().__init__(*args, **kwargs)

    def end_headers(self):
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        super().end_headers()

    def do_GET(self):
        self._serve(send_body=True)

    def do_HEAD(self):
        self._serve(send_body=False)

    def _serve(self, *, send_body: bool):
        path = resolve_static_path(self.path, self.root)
        if path is None:
            self.send_error(404, "File not found")
            return
        try:
            with path.open("rb") as source:
                self.send_response(200)
                self.send_header("Content-Type", MIME_TYPES.get(path.suffix, "application/octet-stream"))
                self.send_header("Content-Length", str(path.stat().st_size))
                self.end_headers()
                if send_body:
                    shutil.copyfileobj(source, self.wfile)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except OSError:
            # Opening can fail if the local file was removed after resolution.
            self.send_error(404, "File not found")

    def log_message(self, format, *args):
        # Avoid echoing arbitrary URL contents into the user's terminal.
        pass


def local_ipv4_addresses() -> list[str]:
    """Find local addresses without contacting a public service."""
    addresses: set[str] = set()
    try:
        for result in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            address = result[4][0]
            if not address.startswith("127.") and address != "0.0.0.0":
                addresses.add(address)
    except OSError:
        pass
    return sorted(addresses)


def parse_port(value: str) -> int:
    try:
        port = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Port must be an integer.") from exc
    if not 1 <= port <= 65535:
        raise argparse.ArgumentTypeError("Port must be between 1 and 65535.")
    return port


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Будни Операционно-Сервисного Менеджера")
    parser.add_argument("--lan", action="store_true", help="Разрешить доступ с телефона в той же Wi-Fi сети")
    parser.add_argument("--no-browser", action="store_true", help="Не открывать браузер автоматически")
    parser.add_argument("--port", type=parse_port, default=8765, help="HTTP-порт, по умолчанию 8765")
    options = parser.parse_args(argv)
    root = application_root()
    missing = [name for name in STATIC_FILES if not (root / name).is_file()]
    if missing:
        print("Не найдены файлы игры. Полностью распакуйте архив в одну папку:")
        print("\n".join(missing))
        return 1
    host = "0.0.0.0" if options.lan else "127.0.0.1"
    try:
        server = ThreadingHTTPServer((host, options.port), partial(GameRequestHandler, root=root))
    except OSError as exc:
        print(f"Не удалось запустить сервер на порту {options.port}: {exc}")
        print("Попробуйте другой порт: python launcher.py --port 8766")
        return 1
    url = f"http://127.0.0.1:{options.port}/"
    print("Будни Операционно-Сервисного Менеджера")
    print(f"На этом компьютере: {url}")
    if options.lan:
        addresses = local_ipv4_addresses()
        print("Телефон и компьютер должны находиться в одной Wi-Fi сети.")
        if addresses:
            print("На телефоне откройте адрес компьютера (подойдёт адрес вашей Wi-Fi сети):")
            for address in addresses:
                print(f"  http://{address}:{options.port}/")
        else:
            print(f"На телефоне: http://<IPv4 компьютера из ipconfig>:{options.port}/")
        print("Для доступа с телефона разрешите Python в частной сети, если Windows спросит.")
        print("Установка и офлайн-режим на телефоне требуют размещения игры по HTTPS.")
    print("Оставьте это окно открытым во время игры. Завершить сервер: Ctrl+C.")
    if not options.no_browser:
        try:
            webbrowser.open(url)
        except webbrowser.Error:
            print("Не удалось открыть браузер. Откройте указанный адрес вручную.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nСервер остановлен.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
