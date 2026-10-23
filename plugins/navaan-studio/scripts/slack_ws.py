"""Author: Navjyot Nishant
Created: 2026-10-23
Last updated: 2026-10-23
Description: the smallest WebSocket client Slack's Socket Mode needs (RFC 6455, client side, text frames), on the standard library only, so the image gains no package (NAV-153).

  ws = connect("wss://wss-primary.slack.com/link/?ticket=...")
  ws.recv(timeout)   the next text message, "" when nothing came in time, None when the server closed the connection
  ws.send(text)      one text frame
  ws.close()

Pings are answered with pongs inside recv(). Continuation frames are joined. Nothing here knows about Slack.
"""
import base64, os, select, socket, ssl, struct, urllib.parse


class Closed(Exception): pass


class WS:
    def __init__(self, sock): self.s = sock; self.buf = b""

    def _read(self, n):
        while len(self.buf) < n:
            chunk = self.s.recv(65536)
            if not chunk: raise Closed("connection closed")
            self.buf += chunk
        out, self.buf = self.buf[:n], self.buf[n:]
        return out

    def _frame(self):
        b1, b2 = self._read(2)
        fin, op, n = b1 & 0x80, b1 & 0x0F, b2 & 0x7F
        if n == 126: n = struct.unpack(">H", self._read(2))[0]
        elif n == 127: n = struct.unpack(">Q", self._read(8))[0]
        mask = self._read(4) if b2 & 0x80 else None
        data = self._read(n)
        if mask: data = bytes(c ^ mask[i % 4] for i, c in enumerate(data))
        return bool(fin), op, data

    def _send(self, op, data):
        n = len(data); head = bytes([0x80 | op])
        head += bytes([0x80 | n]) if n < 126 else (bytes([0x80 | 126]) + struct.pack(">H", n) if n < 65536 else bytes([0x80 | 127]) + struct.pack(">Q", n))
        mask = os.urandom(4)   # a client must mask every frame
        self.s.sendall(head + mask + bytes(c ^ mask[i % 4] for i, c in enumerate(data)))

    def send(self, text): self._send(0x1, text.encode("utf-8"))

    def recv(self, timeout=None):
        if not self.buf and not (getattr(self.s, "pending", None) and self.s.pending()) and not select.select([self.s], [], [], timeout)[0]: return ""   # nothing came in time
        self.s.settimeout(60)   # a frame has started: the rest must follow, else the connection is dropped and made again
        parts = []
        try:
            while True:
                fin, op, data = self._frame()
                if op == 0x9: self._send(0xA, data); continue        # ping: pong with the same data
                if op == 0xA: continue                               # pong
                if op == 0x8: return None                            # the server closes
                parts.append(data)
                if fin: return b"".join(parts).decode("utf-8", "replace")
        except socket.timeout: raise Closed("a message stopped half way")
        except Closed: return None   # expected: the server went away; the caller reconnects

    def close(self):
        try: self._send(0x8, b"")
        except OSError: pass   # expected: already gone
        try: self.s.close()
        except OSError: pass   # expected: already gone


def connect(url, timeout=20):
    u = urllib.parse.urlparse(url)
    if u.scheme not in ("wss", "ws"): raise ValueError("not a websocket address")
    port = u.port or (443 if u.scheme == "wss" else 80)
    raw = socket.create_connection((u.hostname, port), timeout=timeout)
    s = ssl.create_default_context().wrap_socket(raw, server_hostname=u.hostname) if u.scheme == "wss" else raw
    key = base64.b64encode(os.urandom(16)).decode()
    path = (u.path or "/") + ("?" + u.query if u.query else "")
    s.sendall((f"GET {path} HTTP/1.1\r\nHost: {u.hostname}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
               f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n").encode())
    head = b""
    while b"\r\n\r\n" not in head:
        c = s.recv(4096)
        if not c: raise Closed("closed during the handshake")
        head += c
    status = head.split(b"\r\n", 1)[0]
    if b" 101 " not in status + b" ": s.close(); raise Closed("handshake refused: " + status.decode("latin-1")[:80])
    ws = WS(s); ws.buf = head.split(b"\r\n\r\n", 1)[1]
    return ws
