"""Read-only HTTP server exposing homestead JSON.

Author: Marwan Helmy

Uses stdlib only - handy for phone dashboard on LAN.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Optional
from urllib.parse import parse_qs, urlparse

from .storage import JsonStorage


class HomesteadHTTPHandler(BaseHTTPRequestHandler):
    storage: JsonStorage  # set on handler class before serve

    def log_message(self, format, *args):
        pass  # quiet by default

    def _send_json(self, payload, status: int = 200) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Contractor", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_error_json(self, message: str, status: int = 400) -> None:
        self._send_json({"error": message}, status=status)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        qs = parse_qs(parsed.query)

        if path == "/":
            self._send_json({
                "service": "fixlog",
                "endpoints": ["/homestead", "/dwellings", "/health"],
            })
            return

        if path == "/health":
            self._send_json({"ok": True})
            return

        if path == "/homestead":
            self._send_json(self.storage.snapshot())
            return

        if path == "/dwellings":
            active = qs.get("active", ["true"])[0].lower() != "false"
            dwellings = [p.to_dict() for p in self.storage.list_dwellings(active_only=active)]
            self._send_json({"dwellings": dwellings, "count": len(dwellings)})
            return

        if path.startswith("/dwellings/"):
            dwelling_id = path.split("/dwellings/", 1)[1]
            try:
                dwelling = self.storage.get_dwelling(dwelling_id)
            except Exception:
                self._send_error_json("dwelling not found", 404)
                return
            self._send_json(dwelling.to_dict())
            return

        self._send_error_json("not found", 404)

    def do_POST(self) -> None:
        self._send_error_json("read-only server", 405)

    def do_PUT(self) -> None:
        self.do_POST()

    def do_DELETE(self) -> None:
        self.do_POST()


class HomesteadServer:
    def __init__(self, storage: JsonStorage, host: str = "127.0.0.1", port: int = 8765):
        self.storage = storage
        self.host = host
        self.port = port
        self._httpd: Optional[ThreadingHTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    def serve_forever(self) -> None:
        handler = type("BoundHandler", (HomesteadHTTPHandler,), {})
        handler.storage = self.storage
        self._httpd = ThreadingHTTPServer((self.host, self.port), handler)
        self._httpd.serve_forever()

    def start_background(self) -> ThreadingHTTPServer:
        handler = type("BoundHandler", (HomesteadHTTPHandler,), {})
        handler.storage = self.storage
        self._httpd = ThreadingHTTPServer((self.host, self.port), handler)
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()
        return self._httpd

    def stop(self) -> None:
        if self._httpd:
            self._httpd.shutdown()
            self._httpd.server_close()
            self._httpd = None

    @property
    def address(self) -> tuple[str, int]:
        if self._httpd:
            return self._httpd.server_address  # type: ignore
        return (self.host, self.port)


def run_server(homestead_path: str, host: str = "127.0.0.1", port: int = 8765) -> None:
    storage = JsonStorage(homestead_path)
    HomesteadServer(storage, host=host, port=port).serve_forever()
