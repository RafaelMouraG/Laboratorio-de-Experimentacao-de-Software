#!/usr/bin/env python3
"""Implementação de referência do encurtador (contrato v0.1), só biblioteca padrão.

Serve de controle positivo do avaliador: deve satisfazer os 35 requisitos de
classe A. As variantes quebradas em evaluator/controls.py são geradas por
substituição textual deste arquivo; ao alterar trechos citados lá, atualize-as.
"""
import json
import os
import re
import secrets
import signal
import sqlite3
import string
import threading
import time
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

DATA_DIR = os.environ.get("DATA_DIR") or os.path.join(os.getcwd(), "data")
BASE_URL = os.environ.get("BASE_URL") or "http://localhost:8080"
DB_PATH = os.path.join(DATA_DIR, "links.sqlite3")

REDIRECT_STATUS = 302
VALIDATION_STATUS = 422
CODE_LENGTH = 8
CODE_ALPHABET = string.ascii_letters + string.digits
MAX_URL_LENGTH = 2048
MAX_BODY_BYTES = 1 << 20
ALIAS_RE = re.compile(r"[A-Za-z0-9_-]{3,32}")
RESERVED_ALIASES = {"api", "health"}
RFC3339_RE = re.compile(
    r"(\d{4})-(\d{2})-(\d{2})[Tt](\d{2}):(\d{2}):(\d{2})(\.\d+)?([Zz]|[+-]\d{2}:\d{2})")


class ApiError(Exception):
    def __init__(self, status, code, message):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


def validation(message):
    return ApiError(VALIDATION_STATUS, "validation_error", message)


def utc_now():
    return datetime.now(timezone.utc)


def fmt_instant(value):
    value = value.astimezone(timezone.utc)
    spec = "milliseconds" if value.microsecond % 1000 == 0 else "microseconds"
    text = value.isoformat(timespec=spec if value.microsecond else "seconds")
    return text.replace("+00:00", "Z")


def parse_rfc3339(text):
    match = RFC3339_RE.fullmatch(text)
    if not match:
        return None
    year, month, day, hour, minute, second, frac, offset = match.groups()
    micro = int((frac[1:] + "000000")[:6]) if frac else 0
    if offset in ("Z", "z"):
        tz = timezone.utc
    else:
        sign = 1 if offset[0] == "+" else -1
        hours, minutes = int(offset[1:3]), int(offset[4:6])
        if hours > 23 or minutes > 59:
            return None
        tz = timezone(sign * timedelta(hours=hours, minutes=minutes))
    try:
        return datetime(int(year), int(month), int(day), int(hour), int(minute), int(second), micro, tz)
    except ValueError:
        return None


def validate_url(url):
    if not isinstance(url, str):
        raise validation("url deve ser uma string")
    if len(url) > MAX_URL_LENGTH:
        raise validation("url excede 2048 caracteres")
    if any(ch.isspace() or ord(ch) < 0x20 or 0x7F <= ord(ch) <= 0x9F for ch in url):
        raise validation("url contém espaço ou caractere de controle")
    parts = urlsplit(url)
    if parts.scheme.lower() not in ("http", "https"):
        raise validation("url deve usar http ou https")
    if not url[len(parts.scheme):].startswith("://") or not parts.hostname:
        raise validation("url deve ser absoluta e ter host")
    return url


def validate_alias(alias):
    if not isinstance(alias, str) or not ALIAS_RE.fullmatch(alias):
        raise validation("alias deve casar com ^[A-Za-z0-9_-]{3,32}$")
    if alias.lower() in RESERVED_ALIASES:
        raise validation("alias reservado")
    return alias


def validate_expires(value, now):
    if not isinstance(value, str):
        raise validation("expires_at deve ser uma string RFC 3339")
    instant = parse_rfc3339(value)
    if instant is None:
        raise validation("expires_at não é RFC 3339 com fuso")
    if instant <= now:
        raise validation("expires_at deve ser posterior ao instante da requisição")
    return instant


class Conflict(Exception):
    pass


class Store:
    """SQLite em DATA_DIR; um lock serializa as operações, e cada comando confirma sozinho."""

    def __init__(self, path):
        self.db = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.lock = threading.Lock()
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS links ("
            " code TEXT PRIMARY KEY, url TEXT NOT NULL, created_at TEXT NOT NULL,"
            " expires_at TEXT, expires_ts REAL, visits INTEGER NOT NULL DEFAULT 0,"
            " deleted INTEGER NOT NULL DEFAULT 0)")

    def _insert(self, code, url, created, expires):
        try:
            self.db.execute(
                "INSERT INTO links (code, url, created_at, expires_at, expires_ts) VALUES (?, ?, ?, ?, ?)",
                (code, url, fmt_instant(created), expires and fmt_instant(expires),
                 expires and expires.timestamp()))
            return True
        except sqlite3.IntegrityError:
            return False

    def _insert_generated(self, url, created, expires):
        for _ in range(50):
            code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))
            if self._insert(code, url, created, expires):
                return code
        raise ApiError(500, "internal_error", "não foi possível gerar um código livre")

    def create(self, url, alias, expires):
        created = utc_now()
        with self.lock:
            if alias is not None:
                code = alias
                if not self._insert(code, url, created, expires):
                    raise Conflict()
            else:
                code = self._insert_generated(url, created, expires)
        return self.get(code)

    def get(self, code):
        with self.lock:
            row = self.db.execute("SELECT * FROM links WHERE code = ? AND deleted = 0", (code,)).fetchone()
        return row and link_json(row)

    def visit(self, code):
        with self.lock:
            row = self.db.execute("SELECT url, expires_ts FROM links WHERE code = ? AND deleted = 0",
                                  (code,)).fetchone()
            if row is None:
                return "missing", None
            if row["expires_ts"] is not None and time.time() >= row["expires_ts"]:
                return "expired", None
            self.db.execute("UPDATE links SET visits = visits + 1 WHERE code = ?", (code,))
            return "ok", row["url"]

    def delete(self, code):
        with self.lock:
            cursor = self.db.execute("UPDATE links SET deleted = 1 WHERE code = ? AND deleted = 0", (code,))
            return cursor.rowcount == 1

    def close(self):
        with self.lock:
            self.db.close()


def link_json(row):
    return {
        "code": row["code"],
        "url": row["url"],
        "short_url": BASE_URL + "/" + row["code"],
        "created_at": row["created_at"],
        "expires_at": row["expires_at"],
        "visits": row["visits"],
    }


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "encurtador-referencia"
    store = None

    def log_message(self, fmt, *args):  # sem log por requisição
        pass

    def _send(self, status, body=None, headers=()):
        payload = b"" if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        for name, value in headers:
            # Location é enviado em UTF-8, sem normalização; send_header forçaria latin-1.
            self._headers_buffer.append(f"{name}: {value}\r\n".encode("utf-8"))
        if body is not None:
            self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        if payload:
            self.wfile.write(payload)

    def send_error_json(self, status, code, message):
        self._send(status, {"error": {"code": code, "message": message}})

    def _path(self):
        return self.path.split("?", 1)[0].split("#", 1)[0]

    def _read_body(self):
        length = self.headers.get("Content-Length")
        try:
            length = int(length) if length else 0
        except ValueError:
            raise ApiError(400, "invalid_json", "Content-Length inválido")
        if length > MAX_BODY_BYTES:
            raise ApiError(413, "payload_too_large", "corpo maior que 1 MiB")
        return self.rfile.read(length) if length > 0 else b""

    def _dispatch(self, method):
        try:
            body = self._read_body() if method == "POST" else None
            self._route(method, self._path(), body)
        except ApiError as e:
            self.send_error_json(e.status, e.code, e.message)
        except Exception as e:  # noqa: BLE001 — resposta de erro em vez de conexão caída
            self.send_error_json(500, "internal_error", type(e).__name__)

    def do_GET(self):
        self._dispatch("GET")

    def do_POST(self):
        self._dispatch("POST")

    def do_DELETE(self):
        self._dispatch("DELETE")

    def do_PUT(self):
        self._dispatch("PUT")

    def do_PATCH(self):
        self._dispatch("PATCH")

    def _route(self, method, path, body):
        if path == "/health":
            if method != "GET":
                raise ApiError(405, "method_not_allowed", "use GET")
            return self._send(200, {"status": "ok"})
        if path == "/api/links":
            if method != "POST":
                raise ApiError(405, "method_not_allowed", "use POST")
            return self._create(body)
        if path.startswith("/api/links/"):
            code = path[len("/api/links/"):]
            if method == "GET":
                link = self.store.get(code)
                if link is None:
                    raise ApiError(404, "not_found", "link inexistente")
                return self._send(200, link)
            if method == "DELETE":
                if not self.store.delete(code):
                    raise ApiError(404, "not_found", "link inexistente")
                return self._send(204)
            raise ApiError(405, "method_not_allowed", "use GET ou DELETE")
        code = path[1:]
        if method == "GET" and code and "/" not in code:
            state, url = self.store.visit(code)
            if state == "missing":
                raise ApiError(404, "not_found", "link inexistente")
            if state == "expired":
                raise ApiError(410, "expired", "link expirado")
            return self._send(REDIRECT_STATUS, None, [("Location", url)])
        raise ApiError(404, "not_found", "rota inexistente")

    def _create(self, body):
        now = utc_now()
        try:
            data = json.loads(body)
        except ValueError:
            raise ApiError(400, "invalid_json", "corpo não é JSON válido")
        if not isinstance(data, dict):
            raise ApiError(400, "invalid_json", "corpo deve ser um objeto JSON")
        url = validate_url(data.get("url"))
        alias = data.get("alias")
        if alias is not None:
            alias = validate_alias(alias)
        expires = data.get("expires_at")
        if expires is not None:
            expires = validate_expires(expires, now)
        try:
            link = self.store.create(url, alias, expires)
        except Conflict:
            raise ApiError(409, "alias_conflict", "alias já usado")
        self._send(201, link, [("Location", "/api/links/" + link["code"])])


class Server(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 128


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    Handler.store = Store(DB_PATH)
    server = Server(("0.0.0.0", 8080), Handler)

    def stop(signum, frame):
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        server.serve_forever(poll_interval=0.2)
    finally:
        server.server_close()
        Handler.store.close()


if __name__ == "__main__":
    main()
