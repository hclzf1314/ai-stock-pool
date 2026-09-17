from __future__ import annotations

"""Vercel 聚合入口：按 URL path 分发到各 API，静态文件从文件系统返回。"""

import json
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from server_lib import get_quotes
from policy_engine import POLICY_CACHE_SECONDS, get_policy_payload
from mobile_briefing import build_briefing, clamp_limit, load_csv, parse_reference_ids
from server_lib import CACHE_TTL_SECONDS, MARKET_COUNTS, SYMBOLS, WEB_DIR


MIME_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".csv": "text/csv; charset=utf-8",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
    ".md": "text/markdown; charset=utf-8",
}


class handler(BaseHTTPRequestHandler):
    def send_json(self, payload: dict[str, object], status: HTTPStatus = HTTPStatus.OK, cache_seconds: int = 0) -> None:
        body = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        if cache_seconds:
            self.send_header("Cache-Control", f"public, max-age=0, s-maxage={cache_seconds}, stale-while-revalidate=300")
        else:
            self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def send_static(self, path: str) -> None:
        """从部署目录返回静态文件。"""
        root = Path(WEB_DIR).resolve()
        # 去掉查询参数，取路径部分
        rel = path.lstrip("/")
        if not rel or rel == "/":
            rel = "index.html"
        # 防目录穿越
        target = (root / rel).resolve()
        if not str(target).startswith(str(root)):
            self.send_error(HTTPStatus.FORBIDDEN, "Forbidden")
            return
        if target.is_dir():
            target = target / "index.html"
        if not target.is_file():
            self.send_error(HTTPStatus.NOT_FOUND, "Not Found")
            return
        ext = target.suffix.lower()
        ctype = MIME_TYPES.get(ext, "application/octet-stream")
        data = target.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        route = parsed.path
        query = parse_qs(parsed.query)
        try:
            if route == "/api/health":
                self.send_json(
                    {"ok": True, "symbols": len(SYMBOLS), "markets": MARKET_COUNTS, "cacheSeconds": CACHE_TTL_SECONDS},
                    cache_seconds=10,
                )
                return
            if route == "/api/quotes":
                force = query.get("refresh", ["0"]) == ["1"]
                self.send_json(get_quotes(force=force), cache_seconds=60)
                return
            if route == "/api/policy":
                force = query.get("refresh", ["0"]) == ["1"]
                self.send_json(get_policy_payload(force=force), cache_seconds=POLICY_CACHE_SECONDS)
                return
            if route == "/api/mobile/briefing":
                self.send_json(
                    build_briefing(
                        load_csv(WEB_DIR / "discovery-signals.csv"),
                        load_csv(WEB_DIR / "stock-pool.csv"),
                        parse_reference_ids(query.get("reference_ids", [None])),
                        clamp_limit(query.get("limit", [None])),
                    )
                )
                return
            if route.startswith("/api/"):
                self.send_json({"error": "API 不存在", "detail": route}, HTTPStatus.NOT_FOUND)
                return
            # 其他路径：静态文件
            self.send_static(route)
        except Exception as error:
            try:
                self.send_json({"error": "服务暂时不可用", "detail": str(error)}, HTTPStatus.BAD_GATEWAY)
            except Exception:
                pass
