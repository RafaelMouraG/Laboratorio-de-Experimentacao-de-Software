#!/usr/bin/env python3
"""Checks do contrato do encurtador (v0.1), executados no container cliente.

Python 3.11+, só biblioteca padrão. Recebe os parâmetros em JSON pela entrada
padrão e imprime o resultado em JSON. Subcomandos:
  ready SEGUNDOS  consulta GET /health até 200 ou até esgotar o intervalo
  phase1          checks funcionais, de validação e de concorrência, mais a
                  fixture de durabilidade
  durability      observa a fixture depois de um reinício e compara

Cada check verifica só a propriedade do seu requisito. Outras propriedades
usadas como passo intermediário são pré-condições: se falham, o check fica U
(sem resultado conclusivo), e não V. Os checks de status não conferem o corpo
de erro; isso é feito uma única vez em RN13.
"""
import http.client
import json
import math
import re
import secrets
import string
import sys
import threading
import time
from datetime import datetime, timedelta, timezone

RFC3339 = re.compile(
    r"(\d{4})-(\d{2})-(\d{2})[Tt ](\d{2}):(\d{2}):(\d{2})(\.\d+)?([Zz]|[+-]\d{2}:\d{2})")
GENERATED_CODE = re.compile(r"[A-Za-z0-9]{6,12}")
TRICKY_URL = "https://example.com/p%C3%A1gina/a%2Fb?q=a%20b&x=1&y=%c3%a7"
ALNUM = string.ascii_letters + string.digits
LINK_FIELDS = ("code", "url", "short_url", "created_at", "expires_at", "visits")
EVIDENCE_LIMIT = 6


class Violation(Exception):
    def __init__(self, message, *responses):
        super().__init__(message)
        self.responses = responses


class Inconclusive(Violation):
    pass


def rand(n):
    return "".join(secrets.choice(ALNUM) for _ in range(n))


def now():
    return datetime.now(timezone.utc)


def iso_z(value):
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def parse_instant(value):
    """Instante de uma string RFC 3339 com fuso; None se não for válida."""
    if not isinstance(value, str):
        return None
    m = RFC3339.fullmatch(value)
    if not m:
        return None
    year, month, day, hour, minute, second, frac, offset = m.groups()
    micro = int((frac[1:] + "000000")[:6]) if frac else 0
    if offset in ("Z", "z"):
        tz = timezone.utc
    else:
        sign = 1 if offset[0] == "+" else -1
        tz = timezone(sign * timedelta(hours=int(offset[1:3]), minutes=int(offset[4:6])))
    try:
        return datetime(int(year), int(month), int(day), int(hour), int(minute),
                        min(int(second), 59), micro, tz)
    except ValueError:
        return None


def trunc(text, limit):
    return text if len(text) <= limit else text[:limit] + f"…(+{len(text) - limit})"


class Resp:
    def __init__(self, method, path, sent=None):
        self.method, self.path, self.sent = method, path, sent
        self.status, self.headers, self.body, self.error = None, {}, b"", None
        self._json, self._json_ok = None, None

    def header(self, name):
        return self.headers.get(name.lower())

    @property
    def is_redirect(self):
        return self.status in (301, 302, 303, 307, 308) and self.header("location") is not None

    def json(self):
        if self._json_ok is None:
            try:
                self._json, self._json_ok = json.loads(self.body.decode("utf-8")), True
            except (ValueError, UnicodeDecodeError):
                self._json_ok = False
        return self._json if self._json_ok else None

    def json_type(self):
        ctype = (self.header("content-type") or "").split(";")[0].strip().lower()
        return ctype == "application/json"

    def show(self):
        req = f"{self.method} {self.path}"
        if self.sent is not None:
            req += " " + trunc(self.sent if isinstance(self.sent, str) else json.dumps(self.sent, ensure_ascii=False), 160)
        if self.error:
            return f"{req} → sem resposta HTTP ({self.error})"
        res = str(self.status)
        if self.header("location") is not None:
            res += f"; Location: {self.header('location')!r}"
        if self.body:
            ctype = self.header("content-type") or "(sem Content-Type)"
            res += f"; {ctype}; corpo: " + trunc(self.body.decode("utf-8", "replace"), 240)
        return f"{req} → {res}"


class Client:
    def __init__(self, host, port, timeout):
        self.host, self.port, self.timeout = host, port, timeout

    def connection(self, timeout=None):
        return http.client.HTTPConnection(self.host, self.port, timeout=timeout or self.timeout)

    def request(self, method, path, body=None, raw=None, conn=None, timeout=None):
        """body é serializado como JSON; raw é enviado como está (str)."""
        sent = raw if raw is not None else body
        resp = Resp(method, path, sent)
        payload, headers = None, {}
        if raw is not None:
            payload = raw.encode("utf-8")
        elif body is not None:
            payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
        if payload is not None:
            headers["Content-Type"] = "application/json"
        own = conn is None
        conn = conn or self.connection(timeout)
        try:
            conn.request(method, path, body=payload, headers=headers)
            r = conn.getresponse()
            resp.status = r.status
            resp.headers = {k.lower(): v for k, v in r.getheaders()}
            resp.body = r.read()
        except (OSError, http.client.HTTPException) as e:
            resp.error = f"{type(e).__name__}: {e}"[:200]
        finally:
            if own:
                conn.close()
        return resp


class Suite:
    def __init__(self, params):
        self.p = params
        self.client = Client(params["host"], params["port"], params["request_timeout"])
        self.results = {}
        self.error_samples = []  # (error.code esperado, resposta, origem) para RN13
        self.evaluator_errors = []
        self.log = []

    # -- infraestrutura dos checks -------------------------------------------------
    def req(self, method, path, body=None, raw=None):
        r = self.client.request(method, path, body=body, raw=raw)
        self.log.append(r)
        return r

    def post(self, body=None, raw=None):
        return self.req("POST", "/api/links", body=body, raw=raw)

    def alive(self):
        r = self.client.request("GET", "/health", timeout=3)
        return r.status == 200, r

    def run(self, rid, fn):
        ok, probe = self.alive()
        if not ok:
            self.results[rid] = {"verdict": "U", "summary": "Servidor indisponível antes do check; pré-condição não satisfeita",
                                 "evidence": [probe.show()]}
            return
        self.log = []
        try:
            summary = fn()
            verdict, bad = "S", []
        except Inconclusive as e:
            verdict, summary, bad = "U", str(e), list(e.responses)
        except Violation as e:
            verdict, summary, bad = "V", str(e), list(e.responses)
        except Exception as e:  # defeito do avaliador: nunca vira V
            verdict, summary, bad = "U", f"Erro interno do avaliador: {type(e).__name__}: {e}", []
            self.evaluator_errors.append(f"{rid}: {type(e).__name__}: {e}")
        evidence = [r.show() for r in bad]
        for r in self.log:
            if len(evidence) >= EVIDENCE_LIMIT:
                break
            line = r.show()
            if line not in evidence:
                evidence.append(line)
        self.results[rid] = {"verdict": verdict, "summary": summary, "evidence": evidence[:EVIDENCE_LIMIT]}

    def record_error(self, r, expected, origin):
        if r.status is not None and r.status >= 400:
            self.error_samples.append((expected, r, origin))

    def create(self, what="criação do link", **fields):
        """Pré-condição: cria um link e devolve o JSON; falha vira U."""
        fields.setdefault("url", f"https://example.com/{rand(8)}")
        r = self.post(fields)
        body = r.json()
        if r.status != 201 or not isinstance(body, dict) or not isinstance(body.get("code"), str) or not body["code"]:
            raise Inconclusive(f"Pré-condição não satisfeita: {what} não respondeu 201 com code", r)
        return body

    def expect_statuses(self, cases, expected, err_code, origin, send):
        bad = []
        for case in cases:
            r = send(case)
            self.record_error(r, err_code, origin)
            if r.status != expected:
                bad.append(r)
        if bad:
            raise Violation(f"{len(bad)} de {len(cases)} casos sem status {expected}", *bad)
        return f"{len(cases)} casos responderam {expected}"

    def concurrent(self, count, method, path, bodies):
        """Dispara count requisições, cada uma em sua conexão, liberadas juntas por uma barreira."""
        barrier = threading.Barrier(count)
        results = [None] * count

        def worker(i):
            conn = self.client.connection()
            try:
                conn.connect()
            except OSError:
                pass  # a própria requisição registra o erro
            try:
                barrier.wait(timeout=30)
            except threading.BrokenBarrierError:
                pass
            results[i] = self.client.request(method, path, body=bodies[i] if bodies else None, conn=conn)
            conn.close()

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(count)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        return results

    @staticmethod
    def histogram(responses):
        hist = {}
        for r in responses:
            key = str(r.status) if r.error is None else "sem resposta"
            hist[key] = hist.get(key, 0) + 1
        return ", ".join(f"{k}×{v}" for k, v in sorted(hist.items()))

    # -- execução e entrega ------------------------------------------------------
    def rnf05(self):
        base = self.p["base_url"]
        links = [self.create(url="https://example.com/rnf05"),
                 self.create(url="https://example.com/rnf05-alias", alias="bu-" + rand(8))]
        for link in links:
            expected = base + "/" + link["code"]
            if link.get("short_url") != expected:
                raise Violation(f"short_url {link.get('short_url')!r} difere de BASE_URL + '/' + code ({expected!r})", self.log[-1])
            g = self.req("GET", "/api/links/" + link["code"])
            body = g.json()
            if g.status == 200 and isinstance(body, dict) and body.get("short_url") != expected:
                raise Violation(f"short_url na consulta difere de {expected!r}", g)
        return f"short_url = BASE_URL + '/' + code na criação e na consulta (BASE_URL={base})"

    # -- funcionalidades ---------------------------------------------------------
    def rf11(self):
        r = self.req("GET", "/health")
        if r.status != 200:
            raise Violation("GET /health não respondeu 200", r)
        return "GET /health → 200"

    def rf01(self):
        t0 = now()
        r = self.post({"url": TRICKY_URL})
        t1 = now()
        if r.status != 201:
            raise Violation("POST válido não respondeu 201", r)
        body = r.json()
        problems = []
        if not r.json_type():
            problems.append("Content-Type não é application/json")
        if not isinstance(body, dict):
            raise Violation("corpo da criação não é um objeto JSON", r)
        missing = [f for f in LINK_FIELDS if f not in body]
        if missing:
            problems.append("campos ausentes: " + ", ".join(missing))
        code = body.get("code")
        if not isinstance(code, str) or not code:
            problems.append("code não é string não vazia")
        location = r.header("location")
        if isinstance(code, str):
            expected = "/api/links/" + code
            absolute = re.fullmatch(r"https?://[^/?#]+(/[^?#]*)", location or "")
            if location != expected and not (absolute and absolute.group(1) == expected):
                problems.append(f"Location {location!r} não aponta para {expected!r}")
        if body.get("url") != TRICKY_URL:
            problems.append("url devolvida difere da enviada")
        if not isinstance(body.get("short_url"), str):
            problems.append("short_url não é string")
        created = parse_instant(body.get("created_at"))
        tol = timedelta(seconds=self.p["clock_tolerance"])
        if created is None:
            problems.append("created_at não é RFC 3339 com fuso")
        elif not (t0 - tol <= created <= t1 + tol):
            problems.append(f"created_at fora de [{iso_z(t0)}, {iso_z(t1)}] ± {self.p['clock_tolerance']} s")
        if "expires_at" in body and body.get("expires_at") is not None:
            problems.append("expires_at deveria ser null sem expiração")
        visits = body.get("visits")
        if not (isinstance(visits, int) and not isinstance(visits, bool) and visits == 0):
            problems.append("visits não é o inteiro 0")
        if problems:
            raise Violation("; ".join(problems), r)
        return "201 com Location, Content-Type JSON e os seis campos com tipos e valores esperados"

    def rf02(self):
        codes, failed = [], []
        for i in range(self.p["code_samples"]):
            r = self.post({"url": f"https://example.com/rf02/{i}"})
            body = r.json()
            if r.status == 201 and isinstance(body, dict) and isinstance(body.get("code"), str):
                codes.append((body["code"], r))
            else:
                failed.append(r)
        if failed:
            raise Inconclusive(f"Pré-condição não satisfeita: {len(failed)} criações sem alias falharam", failed[0])
        bad = [(c, r) for c, r in codes if not GENERATED_CODE.fullmatch(c)]
        if bad:
            raise Violation(f"{len(bad)} de {len(codes)} códigos fora de [A-Za-z0-9]{{6,12}}, ex.: {bad[0][0]!r}", bad[0][1])
        return f"{len(codes)} códigos gerados casam com [A-Za-z0-9]{{6,12}}"

    def rf03(self):
        alias = "Rf03-" + rand(6)
        for value in (alias, alias.lower()):
            r = self.post({"url": "https://example.com/rf03", "alias": value})
            body = r.json()
            if r.status != 201 or not isinstance(body, dict) or body.get("code") != value:
                raise Violation(f"alias {value!r} não virou o code com 201"
                                + (" (code sensível a maiúsculas)" if value != alias else ""), r)
        return "alias vira o code; variante só em minúsculas é outro code"

    def rf04(self):
        for url in (TRICKY_URL, "http://Example.COM:8443/X?y=Z"):
            link = self.create(url=url)
            r = self.req("GET", "/" + link["code"])
            if r.status != 302:
                raise Violation(f"redirecionamento respondeu {r.status}, não 302", r)
            if r.header("location") != url:
                raise Violation("Location difere byte a byte da url original", r)
        return "302 com Location idêntico à url, inclusive query e percent-encoding"

    def rf05(self):
        link = self.create()
        k = self.p["redirects_k"]
        for _ in range(k):
            r = self.req("GET", "/" + link["code"])
            if not r.is_redirect:
                raise Inconclusive("Pré-condição não satisfeita: GET /{code} não redirecionou", r)
        g = self.req("GET", "/api/links/" + link["code"])
        body = g.json()
        if g.status != 200 or not isinstance(body, dict):
            raise Inconclusive("Pré-condição não satisfeita: consulta do link falhou", g)
        if body.get("visits") != k:
            raise Violation(f"visits = {body.get('visits')!r} depois de {k} redirecionamentos", g)
        return f"visits = {k} depois de {k} redirecionamentos"

    def rf06(self):
        link = self.create()
        path = "/api/links/" + link["code"]

        def series():
            values = []
            for _ in range(3):
                g = self.req("GET", path)
                body = g.json()
                if g.status != 200:
                    raise Violation("consulta de link existente não respondeu 200", g)
                if not g.json_type() or not isinstance(body, dict):
                    raise Violation("consulta não devolveu objeto JSON com Content-Type application/json", g)
                if body.get("code") != link["code"] or body.get("url") != link.get("url"):
                    raise Violation("consulta devolveu code ou url diferentes", g)
                values.append((body.get("visits"), g))
            if len({repr(v) for v, _ in values}) != 1:
                raise Violation("visits mudou entre consultas: " + ", ".join(repr(v) for v, _ in values), values[-1][1])
            return values[0][0]

        first = series()
        r = self.req("GET", "/" + link["code"])
        if r.is_redirect:
            second = series()
            return f"três consultas com visits = {first!r} e, após um redirecionamento, três com {second!r}"
        return f"três consultas com visits = {first!r} (redirecionamento indisponível, só a primeira série)"

    def rf07(self):
        link = self.create()
        code = link["code"]
        d = self.req("DELETE", "/api/links/" + code)
        if d.status != 204:
            raise Violation(f"DELETE respondeu {d.status}, não 204", d)
        if d.body:
            raise Violation("DELETE 204 veio com corpo", d)
        bad = []
        for method, path in (("GET", "/" + code), ("GET", "/api/links/" + code), ("DELETE", "/api/links/" + code)):
            r = self.req(method, path)
            self.record_error(r, "not_found", "RF07")
            if r.status != 404:
                bad.append(r)
        if bad:
            raise Violation(f"{len(bad)} das três operações após a exclusão não responderam 404", *bad)
        return "DELETE → 204 sem corpo; depois, as três operações → 404"

    def rf08(self):
        instant = (now() + timedelta(days=2)).replace(microsecond=0)
        sent = instant.astimezone(timezone(timedelta(hours=-3))).isoformat()
        r = self.post({"url": "https://example.com/rf08", "expires_at": sent})
        if r.status != 201:
            raise Violation(f"expires_at futuro com fuso -03:00 não foi aceito ({r.status})", r)
        body = r.json()
        got = parse_instant(body.get("expires_at")) if isinstance(body, dict) else None
        if got != instant:
            raise Violation(f"expires_at devolvido {body.get('expires_at') if isinstance(body, dict) else None!r} não é o instante {sent}", r)
        g = self.req("GET", "/api/links/" + body["code"])
        gb = g.json()
        if g.status == 200 and isinstance(gb, dict) and parse_instant(gb.get("expires_at")) != instant:
            raise Violation("expires_at na consulta não é o mesmo instante", g)
        return f"{sent} aceito e devolvido como o mesmo instante"

    def rf09_prepare(self):
        """Cria o link que expira e redireciona antes do prazo; o restante vem no fim da fase."""
        state = {"log": []}
        self.rf09_state = state
        try:
            expires = datetime.fromtimestamp(math.ceil(time.time()) + self.p["expiry_seconds"], timezone.utc)
            state["expires"] = expires
            r = self.client.request("POST", "/api/links", body={"url": "https://example.com/rf09", "expires_at": iso_z(expires)})
            state["log"].append(r)
            body = r.json()
            if r.status != 201 or not isinstance(body, dict) or not isinstance(body.get("code"), str):
                state["inconclusive"] = "Pré-condição não satisfeita: criação com expires_at não respondeu 201"
                return
            state["code"] = body["code"]
            before = self.client.request("GET", "/" + body["code"])
            state["log"].append(before)
            state["before"] = before
            if now() >= expires:
                state["inconclusive"] = "Redirecionamento anterior ao prazo terminou depois da expiração; aumentar expiry_seconds"
        except Exception as e:  # noqa: BLE001
            state["inconclusive"] = f"Erro interno do avaliador: {e}"

    def rf09_rf10_after(self):
        state = getattr(self, "rf09_state", {})
        if "code" in state:
            wait = (state["expires"] - now()).total_seconds() + self.p["expiry_margin"]
            if wait > 0:
                time.sleep(wait)
            code = state["code"]
            state["g1"] = self.client.request("GET", "/api/links/" + code)
            state["r1"] = self.client.request("GET", "/" + code)
            state["r2"] = self.client.request("GET", "/" + code)
            state["g2"] = self.client.request("GET", "/api/links/" + code)
            for key in ("r1", "r2"):
                self.record_error(state[key], "expired", "RF09")
        self.run("RF09", self.rf09)
        self.run("RF10", self.rf10)

    def rf09(self):
        s = self.rf09_state
        self.log.extend(s["log"] + [s[k] for k in ("g1", "r1", "r2", "g2") if k in s])
        if "inconclusive" in s:
            raise Inconclusive(s["inconclusive"], *s["log"][-1:])
        if not s["before"].is_redirect:
            raise Violation("antes do prazo, GET /{code} não redirecionou", s["before"])
        bad = [s[k] for k in ("r1", "r2") if s[k].status != 410]
        if bad:
            raise Violation("depois do prazo, GET /{code} não respondeu 410", *bad)
        g1, g2 = s["g1"].json(), s["g2"].json()
        if s["g1"].status != 200 or s["g2"].status != 200 or not isinstance(g1, dict) or not isinstance(g2, dict):
            raise Inconclusive("410 observado, mas a consulta do link expirado falhou; contagem de visitas não verificável", s["g1"])
        if g1.get("visits") != g2.get("visits"):
            raise Violation(f"410 contou visita: {g1.get('visits')!r} → {g2.get('visits')!r}", s["g2"])
        return f"redirecionou antes do prazo ({self.p['expiry_seconds']} s) e respondeu 410 depois, sem contar visita"

    def rf10(self):
        s = self.rf09_state
        if "code" not in s:
            self.log.extend(s["log"])
            raise Inconclusive(s.get("inconclusive", "Pré-condição não satisfeita: link com expiração não criado"), *s["log"][-1:])
        g = s["g1"]
        self.log.append(g)
        body = g.json()
        if g.status != 200 or not isinstance(body, dict):
            raise Violation("consulta de link expirado não respondeu 200 com o link", g)
        if body.get("code") != s["code"] or parse_instant(body.get("expires_at")) != s["expires"]:
            raise Violation("consulta de link expirado devolveu code ou expires_at diferentes", g)
        return "GET /api/links/{code} depois da expiração → 200 com o link"

    # -- validação e erro -------------------------------------------------------
    def rn01(self):
        return self.expect_statuses([{}, {"url": 1}, {"url": None}], 422, "validation_error", "RN01", lambda b: self.post(b))

    def rn02(self):
        urls = ["/a", "example.com", "https://", "ftp://x.org", "javascript:alert(1)"]
        return self.expect_statuses(urls, 422, "validation_error", "RN02", lambda u: self.post({"url": u}))

    def rn03(self):
        prefix = "https://example.com/"
        ok = prefix + "a" * (2048 - len(prefix))
        r = self.post({"url": ok})
        if r.status != 201:
            raise Violation(f"url de 2048 caracteres não foi aceita ({r.status})", r)
        long = prefix + "a" * (2049 - len(prefix))
        r = self.post({"url": long})
        self.record_error(r, "validation_error", "RN03")
        if r.status != 422:
            raise Violation(f"url de 2049 caracteres respondeu {r.status}, não 422", r)
        return "2048 caracteres → 201; 2049 → 422"

    def rn04(self):
        urls = [" https://example.com/a", "https://example.com/a ", "https://example.com/a b",
                "https://example.com/\ta", "https://example.com/\na"]
        return self.expect_statuses(urls, 422, "validation_error", "RN04", lambda u: self.post({"url": u}))

    def rn05(self):
        for url in ("HTTPS://example.com", "Http://example.com/Caminho"):
            r = self.post({"url": url})
            body = r.json()
            if r.status != 201:
                raise Violation(f"esquema em maiúsculas rejeitado ({r.status})", r)
            if not isinstance(body, dict) or body.get("url") != url:
                raise Violation("url devolvida foi alterada", r)
        return "HTTPS:// e Http:// → 201 com url inalterada"

    def rn06(self):
        invalid = ["ab", "a" + rand(32), "ab/c", "ab.c", "ab c", "ação", 123]
        self.expect_statuses(invalid, 422, "validation_error", "RN06",
                             lambda a: self.post({"url": "https://example.com/rn06", "alias": a}))
        for alias in (rand(3), rand(32)):
            r = self.post({"url": "https://example.com/rn06", "alias": alias})
            body = r.json()
            if r.status != 201 or not isinstance(body, dict) or body.get("code") != alias:
                raise Violation(f"alias válido de {len(alias)} caracteres não foi aceito", r)
        return f"{len(invalid)} aliases inválidos → 422; limites de 3 e 32 caracteres → 201"

    def rn07(self):
        return self.expect_statuses(["api", "API", "Health", "health"], 422, "validation_error", "RN07",
                                    lambda a: self.post({"url": "https://example.com/rn07", "alias": a}))

    def rn08(self):
        alias = "rn08-" + rand(8)
        self.create(url="https://example.com/rn08-a", alias=alias)
        r = self.post({"url": "https://example.com/rn08-b", "alias": alias})
        self.record_error(r, "alias_conflict", "RN08")
        if r.status != 409:
            raise Violation(f"segunda criação com o mesmo alias respondeu {r.status}, não 409", r)
        g = self.req("GET", "/api/links/" + alias)
        body = g.json()
        if g.status == 200 and isinstance(body, dict) and body.get("url") != "https://example.com/rn08-a":
            raise Violation("o link original foi sobrescrito pela criação rejeitada", g)
        return "segundo POST com o mesmo alias → 409; link original preservado"

    def rn09(self):
        alias = "rn09-" + rand(8)
        self.create(url="https://example.com/rn09-a", alias=alias)
        d = self.req("DELETE", "/api/links/" + alias)
        if not 200 <= (d.status or 0) < 300:
            raise Inconclusive("Pré-condição não satisfeita: exclusão não respondeu 2xx", d)
        r = self.post({"url": "https://example.com/rn09-b", "alias": alias})
        self.record_error(r, "alias_conflict", "RN09")
        if r.status != 409:
            raise Violation(f"alias de link excluído respondeu {r.status}, não 409", r)
        return "criar, excluir e recriar o mesmo alias → 409"

    def rn10(self):
        current = now().replace(microsecond=0)
        cases = [iso_z(current - timedelta(hours=1)), iso_z(current), "2026-13-01T00:00:00Z",
                 f"{current.year + 1}-01-01T10:00:00", "amanhã", 12345]
        return self.expect_statuses(cases, 422, "validation_error", "RN10",
                                    lambda e: self.post({"url": "https://example.com/rn10", "expires_at": e}))

    def rn11(self):
        return self.expect_statuses(["{", "[]", '"x"', "", "null"], 400, "invalid_json", "RN11",
                                    lambda raw: self.post(raw=raw))

    def rn12(self):
        bad, total = [], 0
        for code in ("zQ" + rand(8), "no.such", "~nada"):
            for method, path in (("GET", "/" + code), ("GET", "/api/links/" + code), ("DELETE", "/api/links/" + code)):
                r = self.req(method, path)
                total += 1
                self.record_error(r, "not_found", "RN12")
                if r.status != 404:
                    bad.append(r)
        if bad:
            raise Violation(f"{len(bad)} de {total} operações com código inexistente não responderam 404", *bad)
        return f"{total} operações com códigos inexistentes → 404"

    def rn13(self):
        if not self.error_samples:
            raise Inconclusive("Nenhuma resposta de erro observada para conferir o formato")
        bad = []
        for expected, r, origin in self.error_samples:
            body = r.json()
            err = body.get("error") if isinstance(body, dict) else None
            ok = (r.json_type() and isinstance(err, dict) and err.get("code") == expected
                  and isinstance(err.get("message"), str))
            if not ok:
                bad.append((expected, r, origin))
        self.log = [r for _, r, _ in self.error_samples[:2]]
        if bad:
            expected, r, origin = bad[0]
            raise Violation(f"{len(bad)} de {len(self.error_samples)} respostas de erro fora do formato; "
                            f"ex.: {origin}, esperado error.code {expected!r}", *[b[1] for b in bad[:3]])
        codes = sorted({e for e, _, _ in self.error_samples})
        return f"{len(self.error_samples)} respostas de erro no formato, com error.code em {codes}"

    def rn14(self):
        url = "https://example.com/rn14"
        first = self.create(url=url)
        r = self.post({"url": url})
        body = r.json()
        if r.status != 201 or not isinstance(body, dict):
            raise Violation(f"segundo POST com a mesma URL respondeu {r.status}, não 201", r)
        if body.get("code") == first["code"]:
            raise Violation("segundo POST devolveu o mesmo code", r)
        return "dois POSTs com a mesma URL → dois links com codes diferentes"

    def rn15(self):
        r = self.post({"url": "https://example.com/rn15", "extra": {"a": [1, 2]}, "nota": "x"})
        if r.status != 201:
            raise Violation(f"POST com campos desconhecidos respondeu {r.status}, não 201", r)
        return "campos desconhecidos ignorados (201)"

    # -- consistência -------------------------------------------------------------
    def rnf06(self):
        n = self.p["n"]
        link = self.create()
        results = self.concurrent(n, "GET", "/" + link["code"], None)
        not_redirect = [r for r in results if not r.is_redirect]
        if not_redirect:
            raise Violation(f"{len(not_redirect)} de {n} redirecionamentos simultâneos falharam ({self.histogram(results)})", *not_redirect[:2])
        g = self.req("GET", "/api/links/" + link["code"])
        body = g.json()
        if g.status != 200 or not isinstance(body, dict):
            raise Inconclusive("Pré-condição não satisfeita: consulta do link falhou", g)
        if body.get("visits") != n:
            raise Violation(f"visits = {body.get('visits')!r} depois de {n} redirecionamentos simultâneos", g)
        return f"{n} redirecionamentos simultâneos → visits = {n}"

    def rnf07(self):
        m = self.p["m"]
        alias = "rnf07-" + rand(8)
        results = self.concurrent(m, "POST", "/api/links", [{"url": f"https://example.com/rnf07/{i}", "alias": alias} for i in range(m)])
        created = [r for r in results if r.status == 201]
        conflicts = [r for r in results if r.status == 409]
        for r in conflicts[:3]:
            self.record_error(r, "alias_conflict", "RNF07")
        if len(created) != 1 or len(conflicts) != m - 1:
            raise Violation(f"esperado 1×201 e {m - 1}×409; obtido {self.histogram(results)}", *(created[:2] or results[:1]))
        g = self.req("GET", "/api/links/" + alias)
        body, winner = g.json(), created[0].json()
        if g.status != 200 or not isinstance(body, dict) or not isinstance(winner, dict) or body.get("url") != winner.get("url"):
            raise Violation("o link consultado não é o da criação aceita", g)
        return f"{m} criações simultâneas com o mesmo alias → 1×201 e {m - 1}×409"

    def rnf08(self):
        p = self.p["p"]
        results = self.concurrent(p, "POST", "/api/links", [{"url": f"https://example.com/rnf08/{i}"} for i in range(p)])
        failed = [r for r in results if r.status != 201 or not isinstance(r.json(), dict)]
        if failed:
            raise Violation(f"{len(failed)} de {p} criações simultâneas não responderam 201 ({self.histogram(results)})", *failed[:2])
        codes = [r.json().get("code") for r in results]
        dupes = sorted({c for c in codes if codes.count(c) > 1}, key=str)
        if dupes:
            same = [r for r in results if r.json().get("code") == dupes[0]]
            raise Violation(f"{len(codes) - len(set(codes))} códigos repetidos entre {p} criações simultâneas, ex.: {dupes[0]!r}", *same[:2])
        return f"{p} criações simultâneas sem alias → {p} códigos distintos"

    # -- durabilidade -------------------------------------------------------------
    def build_fixture(self):
        """Estado a preservar: A (alias, expires_at, visitas), C (código gerado) e B (excluído)."""
        fx = {"log": []}
        try:
            expires = iso_z(now().replace(microsecond=0) + timedelta(days=1))
            a = self.client.request("POST", "/api/links", body={"url": "https://example.com/dur-a?x=1", "alias": "durA-" + rand(8), "expires_at": expires})
            c = self.client.request("POST", "/api/links", body={"url": "https://example.com/dur-c"})
            b = self.client.request("POST", "/api/links", body={"url": "https://example.com/dur-b", "alias": "durB-" + rand(8)})
            fx["log"] += [a, c, b]
            if not all(r.status == 201 and isinstance(r.json(), dict) and isinstance(r.json().get("code"), str) for r in (a, c, b)):
                fx["incomplete"] = "criação dos links da fixture não respondeu 201"
                return fx
            fx["A"], fx["C"], fx["B"] = a.json()["code"], c.json()["code"], b.json()["code"]
            visits = [self.client.request("GET", "/" + fx["A"]) for _ in range(2)]
            d = self.client.request("DELETE", "/api/links/" + fx["B"])
            fx["log"] += visits + [d]
            fx["B_deleted"] = 200 <= (d.status or 0) < 300
            fx["observed"] = observe(self.client, fx)
        except Exception as e:  # noqa: BLE001
            fx["incomplete"] = f"erro interno do avaliador: {e}"
        fx["log"] = [r.show() for r in fx["log"]]
        return fx


def observe(client, fx):
    """Estado visível dos links da fixture, sem alterar visitas."""
    obs = {}
    for key in ("A", "C"):
        g = client.request("GET", "/api/links/" + fx[key])
        body = g.json() if isinstance(g.json(), dict) else {}
        created, expires = parse_instant(body.get("created_at")), parse_instant(body.get("expires_at"))
        obs[key] = {"status": g.status, "url": body.get("url"), "visits": body.get("visits"),
                    "created_at": created and created.isoformat(), "expires_at": expires and expires.isoformat(),
                    "evidence": g.show()}
    g = client.request("GET", "/api/links/" + fx["B"])
    r = client.request("GET", "/" + fx["B"])
    obs["B"] = {"status_api": g.status, "status_redirect": r.status, "evidence": [g.show(), r.show()]}
    return obs


def compare(before, after, fx, check_tombstone, client):
    """Diferenças entre dois estados observados da fixture."""
    problems, evidence = [], []
    for key in ("A", "C"):
        b, a = before[key], after[key]
        if b["status"] != 200:
            return None, [f"link {key} não estava consultável antes do reinício"], [b["evidence"]]
        if a["status"] != 200:
            problems.append(f"link {key} ({fx[key]}) não existe mais: consulta respondeu {a['status']}")
            evidence.append(a["evidence"])
            continue
        diffs = [f for f in ("url", "visits", "created_at", "expires_at") if b[f] != a[f]]
        if diffs:
            problems.append(f"link {key} ({fx[key]}) mudou em {', '.join(diffs)}: "
                            + "; ".join(f"{f} {b[f]!r} → {a[f]!r}" for f in diffs))
            evidence.append(a["evidence"])
    b, a = before["B"], after["B"]
    if fx.get("B_deleted") and b["status_api"] == 404 and b["status_redirect"] == 404:
        if a["status_api"] != 404 or a["status_redirect"] != 404:
            problems.append(f"link excluído {fx['B']} voltou a existir: consulta {a['status_api']}, redirecionamento {a['status_redirect']}")
            evidence += a["evidence"]
        if check_tombstone:
            r = client.request("POST", "/api/links", body={"url": "https://example.com/dur-b2", "alias": fx["B"]})
            if r.status != 409:
                problems.append(f"alias excluído {fx['B']} voltou a ser aceito ({r.status})")
            evidence.append(r.show())
    else:
        evidence.append("exclusão de B não observada antes do reinício; sub-check de exclusão não avaliado")
    return problems, None, evidence


def phase1(params):
    s = Suite(params)
    s.run("RF11", s.rf11)
    s.rf09_prepare()
    for rid, fn in (("RF01", s.rf01), ("RNF05", s.rnf05), ("RF02", s.rf02), ("RF03", s.rf03),
                    ("RF04", s.rf04), ("RF05", s.rf05), ("RF06", s.rf06), ("RF07", s.rf07),
                    ("RF08", s.rf08), ("RN01", s.rn01), ("RN02", s.rn02), ("RN03", s.rn03),
                    ("RN04", s.rn04), ("RN05", s.rn05), ("RN06", s.rn06), ("RN07", s.rn07),
                    ("RN08", s.rn08), ("RN09", s.rn09), ("RN10", s.rn10), ("RN11", s.rn11),
                    ("RN12", s.rn12), ("RN14", s.rn14), ("RN15", s.rn15), ("RNF06", s.rnf06),
                    ("RNF07", s.rnf07), ("RNF08", s.rnf08)):
        s.run(rid, fn)
    fixture = s.build_fixture() if s.alive()[0] else {"incomplete": "servidor indisponível ao montar a fixture", "log": []}
    s.rf09_rf10_after()
    s.run("RN13", s.rn13)
    return {"results": s.results, "fixture": fixture, "evaluator_errors": s.evaluator_errors}


def durability(params):
    client = Client(params["host"], params["port"], params["request_timeout"])
    fx, before = params["fixture"], params["before"]
    after = observe(client, fx)
    problems, incomplete, evidence = compare(before, after, fx, params["check_tombstone"], client)
    if problems is None:
        return {"verdict": "U", "summary": "Pré-condição não satisfeita: " + incomplete[0], "evidence": evidence, "observed": after}
    if problems:
        return {"verdict": "V", "summary": "; ".join(problems), "evidence": evidence[:EVIDENCE_LIMIT], "observed": after}
    return {"verdict": "S", "summary": "links A e C idênticos (url, visits, created_at, expires_at) e B continua excluído",
            "evidence": ([after["A"]["evidence"], after["C"]["evidence"]] + after["B"]["evidence"] + evidence)[:EVIDENCE_LIMIT],
            "observed": after}


def ready(params, seconds):
    client = Client(params["host"], params["port"], 1)
    deadline = time.monotonic() + seconds
    last = None
    while True:
        r = client.request("GET", "/health", timeout=1)
        last = r.show()
        if r.status == 200:
            return {"ready": True, "last": last}
        if time.monotonic() >= deadline:
            return {"ready": False, "last": last}
        time.sleep(0.2)


def main(argv):
    params = json.load(sys.stdin)
    command = argv[1]
    if command == "ready":
        result = ready(params, float(argv[2]))
    elif command == "phase1":
        result = phase1(params)
    elif command == "durability":
        result = durability(params)
    else:
        raise SystemExit(f"subcomando desconhecido: {command}")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main(sys.argv)
