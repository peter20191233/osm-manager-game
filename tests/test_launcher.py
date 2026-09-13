"""Exercise the real HTTP handler, including URL decoding and the allowlist."""

import http.client
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path
import tempfile
import threading
import unittest

from launcher import GameRequestHandler, resolve_static_path


class LauncherTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temporary.name)
        (cls.root / "index.html").write_text("<h1>OSM</h1>", encoding="utf-8")
        (cls.root / "game.py").write_bytes(b"RATING = 1\n")
        (cls.root / "manifest.webmanifest").write_text('{"name":"OSM"}', encoding="utf-8")
        (cls.root / "launcher.py").write_text("PRIVATE_MARKER", encoding="utf-8")
        (cls.root / ".secret").write_text("PRIVATE_MARKER", encoding="utf-8")
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), partial(GameRequestHandler, root=cls.root))
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=3)
        cls.temporary.cleanup()

    def request(self, path, method="GET"):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_address[1], timeout=3)
        try:
            connection.request(method, path)
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            connection.close()

    def test_root_query_and_head(self):
        status, headers, body = self.request("/?version=2&path=../../.secret")
        self.assertEqual(status, 200)
        self.assertEqual(body, b"<h1>OSM</h1>")
        self.assertEqual(headers["Cache-Control"], "no-cache")
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        status, headers, body = self.request("/index.html", "HEAD")
        self.assertEqual(status, 200)
        self.assertEqual(body, b"")
        self.assertEqual(int(headers["Content-Length"]), len(b"<h1>OSM</h1>"))

    def test_python_and_manifest_mime_types(self):
        status, headers, body = self.request("/game.py?v=1")
        self.assertEqual(status, 200)
        self.assertEqual(body, b"RATING = 1\n")
        self.assertTrue(headers["Content-Type"].startswith("text/x-python"))
        status, headers, _ = self.request("/manifest.webmanifest")
        self.assertEqual(status, 200)
        self.assertTrue(headers["Content-Type"].startswith("application/manifest+json"))

    def test_private_missing_and_traversal_are_not_served(self):
        paths = (
            "/launcher.py", "/.secret", "/tests/", "/assets/", "/engine.py",
            "/../launcher.py", "/%2e%2e/launcher.py", "/%252e%252e/launcher.py",
            "/assets/../launcher.py", "/assets/%2e%2e/index.html",
            "/assets%5c..%5clauncher.py", "/index.html%00", "/%ff",
            "/.git/config", "/index.html/extra", "/%2findex.html",
        )
        for path in paths:
            with self.subTest(path=path):
                status, _, body = self.request(path)
                self.assertEqual(status, 404)
                self.assertNotIn(b"PRIVATE_MARKER", body)

    def test_absolute_request_targets_are_rejected(self):
        for target in ("//example.com/index.html", "https://example.com/index.html", "index.html"):
            with self.subTest(target=target):
                self.assertIsNone(resolve_static_path(target, self.root))

    def test_post_cannot_write(self):
        status, _, _ = self.request("/game.py", "POST")
        self.assertEqual(status, 501)
        self.assertEqual((self.root / "game.py").read_text(encoding="utf-8"), "RATING = 1\n")


if __name__ == "__main__":
    unittest.main()
