"""Read-only media endpoint for an existing HTTPS reverse proxy. Never serves project files."""
import os
import re
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit


def serve(host="127.0.0.1", port=8787):
    root = Path(os.getenv("PUBLIC_MEDIA_DIR", "data/public-media")).resolve()
    root.mkdir(parents=True, exist_ok=True)

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(root), **kwargs)

        def send_head(self):
            route = urlsplit(self.path).path
            if not re.fullmatch(r"/[0-9a-f]{12}/[1-7]\.(?:mp4|jpg|jpeg)", route):
                self.send_error(404)
                return None
            path = root / route.lstrip("/")
            if not path.resolve().is_relative_to(root) or path.is_symlink() or path.parent.is_symlink():
                self.send_error(404)
                return None
            return super().send_head()

        def log_message(self, *args):
            pass

    print(f"Serving only staged Instagram assets at http://{host}:{port}; configure your HTTPS reverse proxy.", flush=True)
    ThreadingHTTPServer((host, port), Handler).serve_forever()
