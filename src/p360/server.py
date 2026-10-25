"""OpenAI-compatible HTTP front for the gateway (stdlib only).

POST /v1/chat/completions   {"model": "auto"|"open"|"closed", "messages": [...], "user": "<tenant>"}
GET  /v1/models, GET /healthz
Auth: bearer token compared with P360_GATEWAY_TOKEN (constant-time). Bodies over 64 KB are rejected.
"""

from __future__ import annotations

import hmac
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .gateway import Gateway
from .guardrails import get_logger, safe_error

MAX_BODY = 64 * 1024
log = get_logger("p360.server")


def make_handler(gw: Gateway):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):  # route access logs through the redacting logger
            log.info("%s", self.requestline)

        def _send(self, code: int, obj: dict):
            body = json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _authed(self) -> bool:
            want = os.environ.get("P360_GATEWAY_TOKEN")
            if not want:
                return True  # local dev only; the Helm chart always sets a token
            got = self.headers.get("Authorization", "").removeprefix("Bearer ")
            return hmac.compare_digest(got, want)

        def do_GET(self):
            if self.path == "/healthz":
                return self._send(200, {"status": "ok"})
            if self.path == "/v1/models":
                return self._send(200, {"object": "list", "data": [{"id": m, "object": "model"} for m in ("auto", "open", "closed")]})
            self._send(404, {"error": "not found"})

        def do_POST(self):
            if self.path != "/v1/chat/completions":
                return self._send(404, {"error": "not found"})
            if not self._authed():
                return self._send(401, {"error": "unauthorized"})
            n = int(self.headers.get("Content-Length", "0"))
            if n > MAX_BODY:
                return self._send(413, {"error": "body too large"})
            try:
                req = json.loads(self.rfile.read(n))
                force = req.get("model") if req.get("model") in ("open", "closed") else None
                r = gw.chat(req["messages"], tenant=str(req.get("user", "default")), max_tokens=int(req.get("max_tokens", 256)), force=force)
            except Exception as e:  # never leak internals
                log.warning("bad request: %s", safe_error(e))
                return self._send(400, {"error": "bad request"})
            if r.blocked:
                return self._send(400, {"error": r.text, "code": r.blocked})
            if not r.ok:
                return self._send(503, {"error": r.text})
            self._send(
                200,
                {
                    "object": "chat.completion",
                    "model": r.model,
                    "choices": [{"index": 0, "message": {"role": "assistant", "content": r.text}, "finish_reason": "stop"}],
                    "p360": {"route": r.route, "reason": r.reason, "cost_usd": r.cost_usd, "pii_redacted": len(r.pii_in)},
                },
            )

    return H


def serve(gw: Gateway, host: str = "127.0.0.1", port: int = 8360) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), make_handler(gw))
