"""Proxy CONNECT do piloto: só TLS a destinos explícitos; não registra conteúdo."""
import os
import select
import socket
import socketserver

ALLOWED = frozenset(os.environ["PILOT_ALLOWED_HOSTS"].split(","))


class Tunnel(socketserver.StreamRequestHandler):
    def handle(self):
        self.connection.settimeout(15)
        first = self.rfile.readline(8193).decode("ascii", errors="replace").strip()
        if len(first) > 8192:
            return
        for _ in range(100):
            if self.rfile.readline(8193) in (b"\r\n", b"\n", b""):
                break
        parts = first.split()
        target = parts[1] if len(parts) == 3 else ""
        host, _, port = target.rpartition(":")
        if len(parts) != 3 or parts[0] != "CONNECT" or host not in ALLOWED or port != "443":
            self.wfile.write(b"HTTP/1.1 403 Forbidden\r\nContent-Length: 0\r\n\r\n")
            print("DENY", target[:255], flush=True)
            return
        try:
            remote = socket.create_connection((host, 443), timeout=20)
        except OSError:
            self.wfile.write(b"HTTP/1.1 502 Bad Gateway\r\nContent-Length: 0\r\n\r\n")
            print("CONNECT_FAILED", host, flush=True)
            return
        with remote:
            self.wfile.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
            self.wfile.flush()
            print("ALLOW", host, flush=True)
            self.connection.settimeout(120)
            remote.settimeout(120)
            try:
                while True:
                    readable, _, _ = select.select([self.connection, remote], [], [], 120)
                    if not readable:
                        return
                    for source in readable:
                        chunk = source.recv(65536)
                        if not chunk:
                            return
                        (remote if source is self.connection else self.connection).sendall(chunk)
            except OSError:
                return


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


if __name__ == "__main__":
    with Server(("0.0.0.0", 8080), Tunnel) as server:
        server.serve_forever()
