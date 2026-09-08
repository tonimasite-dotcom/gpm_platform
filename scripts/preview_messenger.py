"""Serve a built Flutter app locally with demo-only public configuration."""

import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from pathlib import Path
from urllib.parse import unquote, urlsplit


DEMO_CONFIG = b"GPM_APP_MODE=demo\nGPM_APP_API_URL=\nGPM_APP_API_TOKEN=\n"


class PreviewHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def send_head(self):
        resource = Path(self.translate_path(self.path)).resolve()
        if not resource.is_relative_to(Path(self.directory).resolve()):
            self.send_error(403)
            return None
        # Never serve the build's original API configuration, even for HEAD.
        if resource.name == ".env":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(DEMO_CONFIG)))
            self.end_headers()
            return BytesIO(DEMO_CONFIG)
        if not resource.exists() and not Path(unquote(urlsplit(self.path).path)).suffix:
            self.path = "/index.html"
        return super().send_head()

    def list_directory(self, path):
        self.send_error(403)
        return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--directory", type=Path,
        default=Path(r"C:\tmp\gpm-messenger-web-20260908-a97e110"),
        help="Flutter web build directory (use an ASCII path on Windows)",
    )
    args = parser.parse_args()
    root = args.directory.resolve()
    if not (root / "index.html").is_file():
        parser.error("Preview build is missing; build Flutter web first")
    with ThreadingHTTPServer(
        ("127.0.0.1", 8090), partial(PreviewHandler, directory=str(root))
    ) as server:
        print("Messenger demo: http://127.0.0.1:8090/", flush=True)
        server.serve_forever()


if __name__ == "__main__":
    main()
