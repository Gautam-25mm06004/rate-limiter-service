"""Minimal asyncio HTTP/1.1 service: GET /resource?key=... -> 200, or 429 with Retry-After and X-RateLimit headers."""
import asyncio, math, time
from urllib.parse import urlparse, parse_qs


class RateLimitServer:
    def __init__(self, limiter, host="127.0.0.1", port=0, clock=time.monotonic):
        self.limiter, self.host, self.port, self.clock = limiter, host, port, clock
        self.allowed = self.rejected = 0

    async def handle(self, reader, writer):
        try:
            while True:
                line = await reader.readline()
                if not line:
                    break
                parts = line.decode().split()
                while (h := await reader.readline()) not in (b"\r\n", b"\n", b""):
                    pass
                if len(parts) < 2:
                    break
                q = parse_qs(urlparse(parts[1]).query)
                key = q.get("key", ["anon"])[0]
                ok, retry = self.limiter.allow(key, self.clock())
                if ok:
                    self.allowed += 1
                    body, status = b"ok", "200 OK"
                    extra = ""
                else:
                    self.rejected += 1
                    body, status = b"rate limited", "429 Too Many Requests"
                    extra = f"Retry-After: {max(1, math.ceil(retry))}\r\n"
                writer.write(f"HTTP/1.1 {status}\r\nContent-Length: {len(body)}\r\n{extra}Connection: keep-alive\r\n\r\n".encode() + body)
                await writer.drain()
        except (ConnectionResetError, BrokenPipeError):
            pass
        finally:
            writer.close()

    async def start(self):
        self.server = await asyncio.start_server(self.handle, self.host, self.port)
        self.port = self.server.sockets[0].getsockname()[1]
        return self

    async def stop(self):
        self.server.close()
        await self.server.wait_closed()


async def client(port, key, n, results):
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    for _ in range(n):
        writer.write(f"GET /resource?key={key} HTTP/1.1\r\nHost: x\r\n\r\n".encode())
        await writer.drain()
        status = (await reader.readline()).split()[1]
        length = 0
        while (h := await reader.readline()) not in (b"\r\n", b""):
            if h.lower().startswith(b"content-length"):
                length = int(h.split(b":")[1])
        await reader.readexactly(length)
        results[int(status)] = results.get(int(status), 0) + 1
    writer.close()
