from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

from server_lib import get_quotes


class handler(BaseHTTPRequestHandler):
    def send_json(self, payload: dict[str, object], status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "public, max-age=0, s-maxage=60, stale-while-revalidate=300")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        try:
            query = parse_qs(urlparse(self.path).query)
            force = query.get("refresh", ["0"])[0] == "1"
            self.send_json(get_quotes(force=force))
        except Exception as error:
            self.send_json(
                {"error": "行情暂时不可用", "detail": str(error), "quotes": {}},
                HTTPStatus.BAD_GATEWAY,
            )
