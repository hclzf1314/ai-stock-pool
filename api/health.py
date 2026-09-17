from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler

from server_lib import CACHE_TTL_SECONDS, MARKET_COUNTS, SYMBOLS


class handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        body = json.dumps(
            {
                "ok": True,
                "symbols": len(SYMBOLS),
                "markets": MARKET_COUNTS,
                "cacheSeconds": CACHE_TTL_SECONDS,
                "policyEndpoint": "/api/policy",
            },
            ensure_ascii=False,
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)
