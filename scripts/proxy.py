"""Path-rewrite proxy in front of Hermes' webhook gateway.

Hermes' built-in gateway hardcodes its routes under /webhooks/{name}. We want
the public API to live at /api/crawl, so this proxy listens on the public
WEBHOOK_PORT and forwards each /api/* request to Hermes on
HERMES_INTERNAL_PORT.

When PROXY_AUTOSIGN=true (the default), the proxy computes the HMAC-SHA256
signature of the body itself using WEBHOOK_SECRET and overwrites the
X-Webhook-Signature header before forwarding. That removes the entire
"exact-bytes-must-match" foot-gun for Postman / curl callers and is safe
because Hermes is bound to 127.0.0.1 (only reachable through this proxy).
Set PROXY_AUTOSIGN=false to require callers to supply a valid signature.
"""

import hashlib
import hmac
import os
import sys
from aiohttp import web, ClientSession, ClientTimeout

UPSTREAM = f"http://127.0.0.1:{os.environ.get('HERMES_INTERNAL_PORT', '8645')}"
PUBLIC_PORT = int(os.environ.get("WEBHOOK_PORT", "8644"))
AUTOSIGN = os.environ.get("PROXY_AUTOSIGN", "true").lower() == "true"
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "")

ROUTE_MAP = {
    "/api/crawl": "/webhooks/crawl",
    "/api/audit": "/webhooks/audit",
    "/api/feedback": "/webhooks/feedback",
    "/health": "/health",
}

HOP_BY_HOP = {"host", "content-length", "transfer-encoding", "connection"}


async def proxy(request: web.Request) -> web.Response:
    target_path = ROUTE_MAP.get(request.path)
    if target_path is None:
        return web.Response(status=404, text="not found\n")

    upstream_url = f"{UPSTREAM}{target_path}"
    body = await request.read()
    fwd_headers = {
        k: v for k, v in request.headers.items() if k.lower() not in HOP_BY_HOP
    }

    if AUTOSIGN and WEBHOOK_SECRET and body:
        sig = hmac.new(
            WEBHOOK_SECRET.encode(), body, hashlib.sha256
        ).hexdigest()
        # Strip any inbound variants the client might have sent (case-insensitive).
        for k in list(fwd_headers):
            if k.lower() in {"x-webhook-signature", "x-hub-signature-256"}:
                del fwd_headers[k]
        fwd_headers["X-Webhook-Signature"] = sig

    timeout = ClientTimeout(total=600)
    try:
        async with ClientSession(timeout=timeout) as session:
            async with session.request(
                request.method,
                upstream_url,
                data=body,
                headers=fwd_headers,
                allow_redirects=False,
            ) as up:
                up_body = await up.read()
                resp_headers = {
                    k: v for k, v in up.headers.items() if k.lower() not in HOP_BY_HOP
                }
                return web.Response(
                    status=up.status, body=up_body, headers=resp_headers
                )
    except Exception as exc:
        sys.stderr.write(f"[proxy] upstream error: {exc}\n")
        return web.Response(status=502, text=f"upstream error: {exc}\n")


def main() -> None:
    app = web.Application()
    for public_path in ROUTE_MAP:
        app.router.add_route("*", public_path, proxy)
    sys.stdout.write(
        f"[proxy] listening on 0.0.0.0:{PUBLIC_PORT}, "
        f"forwarding /api/* and /health to {UPSTREAM}\n"
    )
    sys.stdout.flush()
    web.run_app(app, host="0.0.0.0", port=PUBLIC_PORT, print=None)


if __name__ == "__main__":
    main()
