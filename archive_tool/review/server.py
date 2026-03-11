from __future__ import annotations

import argparse
import json
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from .actions import delete_and_sync

def build_handler(output_dir: Path, state_file: Path):
    class ReviewHandler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(output_dir), **kwargs)

        def end_headers(self):
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            super().end_headers()

        def do_OPTIONS(self):
            self.send_response(HTTPStatus.NO_CONTENT)
            self.end_headers()

        def do_POST(self):
            parsed = urlparse(self.path)
            if parsed.path != "/api/delete":
                self.send_error(HTTPStatus.NOT_FOUND, "Not Found")
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(length) if length > 0 else b"{}"
                body = json.loads(raw.decode("utf-8"))
            except Exception:
                self.send_error(HTTPStatus.BAD_REQUEST, "Invalid JSON")
                return

            paths = body.get("paths", [])
            if not isinstance(paths, list):
                self.send_error(HTTPStatus.BAD_REQUEST, "paths must be array")
                return

            payload = delete_and_sync(
                [str(x) for x in paths],
                output_dir=output_dir,
                state_file=state_file,
                source="http-api",
                quick_reexport=True,
            )
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    return ReviewHandler


def main() -> None:
    parser = argparse.ArgumentParser(description="本地审核页服务（支持直接删除并同步状态）")
    parser.add_argument("--output-dir", required=True, help="审核文件目录（包含 作品归档审核页.html）")
    parser.add_argument("--state-file", required=True, help="状态文件 archive_state.json")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=18765)
    args = parser.parse_args()

    output_dir = Path(args.output_dir).resolve()
    state_file = Path(args.state_file).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    state_file.parent.mkdir(parents=True, exist_ok=True)
    handler = build_handler(output_dir, state_file)
    server = ThreadingHTTPServer((args.host, args.port), handler)
    print(f"[ReviewServer] serving: http://{args.host}:{args.port}/作品归档审核页.html")
    print(f"[ReviewServer] output_dir={output_dir}")
    print(f"[ReviewServer] state_file={state_file}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
