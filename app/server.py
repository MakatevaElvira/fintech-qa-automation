"""Demo lending back-office: JSON API + one UI page (standard library only).

Endpoints
    GET  /health
    POST /api/auth/login              username + password -> session cookie
    GET  /api/applications            filters: product, status, risk_flags, amount_min, amount_max, page
    GET  /api/applications/{uuid}
    PUT  /api/applications/{uuid}     change status / number of risk flags (used by test data factory)
    GET  /applications                UI page (needs session cookie)

Run:  python -m app.server  ->  http://127.0.0.1:8080/applications
"""

from __future__ import annotations

import argparse
import json
import secrets
import sqlite3
import tempfile
import threading
import time
import urllib.request
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from app.db import PRODUCTS, STATUSES, connect, seed

STATIC = Path(__file__).parent / "static"
DEMO_USERS = {"qa-bot": "demo-password"}  # public demo credentials of the demo service
PAGE_SIZE = 20
TABLE_DELAY_SEC = 0.2  # imitate a real backend so tests must wait properly


class State:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.sessions: set[str] = set()
        self.lock = threading.Lock()

    def conn(self) -> sqlite3.Connection:
        return connect(self.db_path)


def application_to_dict(conn: sqlite3.Connection, row: sqlite3.Row) -> dict:
    checks = conn.execute(
        "SELECT uuid, check_type, product, risk_flag, ai_verdict FROM checks WHERE application_id = ? ORDER BY id",
        (row["id"],),
    ).fetchall()
    return {
        "uuid": row["uuid"],
        "external_id": row["external_id"],
        "client_name": row["client_name"],
        "product": row["product"],
        "status": row["status"],
        "channel": row["channel"],
        "amount": row["amount"],
        "created_at": row["created_at"],
        "risk_flags": sum(c["risk_flag"] for c in checks),
        "checks": [
            {
                "uuid": c["uuid"],
                "check_type": c["check_type"],
                "product": c["product"],
                "risk_flag": bool(c["risk_flag"]),
                "ai_verdict": c["ai_verdict"],
            }
            for c in checks
        ],
    }


class ApiError(Exception):
    def __init__(self, status: int, message: str, fields: dict | None = None):
        super().__init__(message)
        self.status, self.message, self.fields = status, message, fields


def build_filters(query: dict[str, list[str]]) -> tuple[str, list]:
    where, params = [], []
    errors: dict[str, str] = {}

    products = [p for v in query.get("product", []) for p in v.split(",") if p]
    if bad := [p for p in products if p not in PRODUCTS]:
        errors["product"] = f"unknown values: {bad}"
    elif products:
        marks = ",".join("?" * len(products))
        where.append(f"a.id IN (SELECT application_id FROM checks WHERE product IN ({marks}))")
        params += products

    statuses = [s for v in query.get("status", []) for s in v.split(",") if s]
    if bad := [s for s in statuses if s not in STATUSES]:
        errors["status"] = f"unknown values: {bad}"
    elif statuses:
        where.append(f"a.status IN ({','.join('?' * len(statuses))})")
        params += statuses

    risk = query.get("risk_flags", [""])[0]
    if risk == "with":
        where.append("a.id IN (SELECT application_id FROM checks WHERE risk_flag = 1)")
    elif risk == "without":
        where.append("a.id NOT IN (SELECT application_id FROM checks WHERE risk_flag = 1)")
    elif risk:
        errors["risk_flags"] = "must be 'with' or 'without'"

    for name, op in (("amount_min", ">="), ("amount_max", "<=")):
        raw = query.get(name, [""])[0]
        if raw == "":
            continue
        if not raw.isdigit():
            errors[name] = "must be a non-negative integer"
            continue
        where.append(f"a.amount {op} ?")
        params.append(int(raw))

    if errors:
        raise ApiError(422, "validation failed", errors)
    return (" WHERE " + " AND ".join(where)) if where else "", params


def make_handler(state: State):
    class Handler(BaseHTTPRequestHandler):
        server_version = "DemoLendingBackOffice/1.0"

        def log_message(self, *args):
            pass

        # ---------- helpers ----------
        def _json(self, status: int, body: dict, cookie: str | None = None):
            data = json.dumps(body, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            if cookie:
                self.send_header("Set-Cookie", f"session={cookie}; Path=/; HttpOnly; SameSite=Lax")
            self.end_headers()
            self.wfile.write(data)

        def _html(self, status: int, html: str):
            data = html.encode()
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _authorized(self) -> bool:
            cookie = SimpleCookie(self.headers.get("Cookie", ""))
            return "session" in cookie and cookie["session"].value in state.sessions

        def _body(self) -> dict:
            length = int(self.headers.get("Content-Length", 0))
            try:
                body = json.loads(self.rfile.read(length) or b"{}")
            except ValueError as exc:
                raise ApiError(400, "body must be JSON") from exc
            if not isinstance(body, dict):
                raise ApiError(400, "body must be a JSON object")
            return body

        def _dispatch(self, method: str):
            url = urlparse(self.path)
            try:
                if method == "GET" and url.path == "/health":
                    return self._json(200, {"status": "ok"})
                if method == "POST" and url.path == "/api/auth/login":
                    return self._login()
                if method == "GET" and url.path == "/applications":
                    if not self._authorized():
                        return self._html(401, "<h1>401 Unauthorized</h1>")
                    return self._html(200, (STATIC / "applications.html").read_text(encoding="utf-8"))
                if url.path.startswith("/api/"):
                    if not self._authorized():
                        raise ApiError(401, "unauthorized")
                    if method == "GET" and url.path == "/api/applications":
                        return self._list(parse_qs(url.query))
                    if url.path.startswith("/api/applications/"):
                        app_uuid = url.path.rsplit("/", 1)[-1]
                        if method == "GET":
                            return self._get(app_uuid)
                        if method == "PUT":
                            return self._update(app_uuid)
                raise ApiError(404, "not found")
            except ApiError as err:
                body = {"error": err.message}
                if err.fields:
                    body["fields"] = err.fields
                return self._json(err.status, body)

        def do_GET(self):
            self._dispatch("GET")

        def do_POST(self):
            self._dispatch("POST")

        def do_PUT(self):
            self._dispatch("PUT")

        # ---------- endpoints ----------
        def _login(self):
            body = self._body()
            missing = {f: "field is required" for f in ("username", "password") if not body.get(f)}
            if missing:
                raise ApiError(422, "validation failed", missing)
            if DEMO_USERS.get(body["username"]) != body["password"]:
                raise ApiError(401, "invalid username or password")
            token = secrets.token_hex(16)
            with state.lock:
                state.sessions.add(token)
            return self._json(201, {"status": "ok"}, cookie=token)

        def _list(self, query: dict[str, list[str]]):
            where, params = build_filters(query)
            page_raw = query.get("page", ["1"])[0]
            if not page_raw.isdigit() or int(page_raw) < 1:
                raise ApiError(422, "validation failed", {"page": "must be a positive integer"})
            page = int(page_raw)
            time.sleep(TABLE_DELAY_SEC)
            conn = state.conn()
            total = conn.execute(f"SELECT COUNT(*) FROM applications a{where}", params).fetchone()[0]
            rows = conn.execute(
                f"SELECT a.* FROM applications a{where} ORDER BY a.id DESC LIMIT ? OFFSET ?",
                [*params, PAGE_SIZE, (page - 1) * PAGE_SIZE],
            ).fetchall()
            items = [application_to_dict(conn, r) for r in rows]
            conn.close()
            return self._json(200, {"total": total, "page": page, "page_size": PAGE_SIZE, "items": items})

        def _get(self, app_uuid: str):
            conn = state.conn()
            row = conn.execute("SELECT * FROM applications WHERE uuid = ?", (app_uuid,)).fetchone()
            if row is None:
                raise ApiError(404, "application not found")
            body = application_to_dict(conn, row)
            conn.close()
            return self._json(200, body)

        def _update(self, app_uuid: str):
            body = self._body()
            errors = {}
            if "status" in body and body["status"] not in STATUSES:
                errors["status"] = f"must be one of {STATUSES}"
            flags = body.get("risk_flags")
            if flags is not None and (not isinstance(flags, int) or isinstance(flags, bool) or flags < 0):
                errors["risk_flags"] = "must be a non-negative integer"
            if errors:
                raise ApiError(422, "validation failed", errors)
            with state.lock:
                conn = state.conn()
                row = conn.execute("SELECT id FROM applications WHERE uuid = ?", (app_uuid,)).fetchone()
                if row is None:
                    raise ApiError(404, "application not found")
                if "status" in body:
                    conn.execute("UPDATE applications SET status = ? WHERE id = ?", (body["status"], row["id"]))
                if flags is not None:
                    check_ids = [
                        c[0]
                        for c in conn.execute(
                            "SELECT id FROM checks WHERE application_id = ? ORDER BY id", (row["id"],)
                        )
                    ]
                    if flags > len(check_ids):
                        raise ApiError(409, f"application has only {len(check_ids)} checks")
                    for i, check_id in enumerate(check_ids):
                        conn.execute("UPDATE checks SET risk_flag = ? WHERE id = ?", (int(i < flags), check_id))
                conn.commit()
                row = conn.execute("SELECT * FROM applications WHERE id = ?", (row["id"],)).fetchone()
                result = application_to_dict(conn, row)
                conn.close()
            return self._json(200, result)

    return Handler


def start(host: str = "127.0.0.1", port: int = 0, db_path: Path | None = None) -> tuple[ThreadingHTTPServer, Path]:
    """Seed a fresh DB and start the server in a background thread (port=0 -> free port)."""
    db_path = db_path or Path(tempfile.mkdtemp()) / "lending.db"
    seed(db_path)
    server = ThreadingHTTPServer((host, port), make_handler(State(db_path)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, db_path


def preflight(base_url: str, timeout: float = 5) -> None:
    """Fail fast if the service is not reachable (used in CI before tests)."""
    with urllib.request.urlopen(f"{base_url}/health", timeout=timeout) as resp:
        if resp.status != 200:
            raise SystemExit(f"service unhealthy: HTTP {resp.status}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()
    srv, db = start(port=args.port)
    print(f"Lending back-office on http://127.0.0.1:{args.port}/applications (db: {db})")
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        srv.shutdown()
