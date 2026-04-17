import json
import mimetypes
import time
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.parse import parse_qs, urlparse

from app import AppState
from events import format_log

STATIC_DIR = Path(__file__).parent / "static"


def _classify_target(snap: dict) -> str:
    if snap["total"] == 0:
        return "init"
    if snap["consecutive_fail"] >= 3:
        return "down"
    if snap["recent_loss_pct"] > 10 or snap["consecutive_fail"] > 0:
        return "degraded"
    return "ok"


def _classify_group(snaps: list[dict]) -> str:
    if not snaps:
        return "none"
    if any(s["total"] == 0 for s in snaps):
        return "init"
    if any(s["consecutive_fail"] >= 3 for s in snaps):
        return "down"
    if any(s["recent_loss_pct"] > 10 or s["consecutive_fail"] > 0 for s in snaps):
        return "degraded"
    return "ok"


def build_status(app: AppState) -> dict:
    targets_out: list[dict] = []
    groups: dict[str, list[dict]] = {"ISP1": [], "ISP2": [], "LAN": []}

    for target in app.config.targets():
        kinds: list[tuple[str, str]] = []
        if target.icmp:
            kinds.append(("icmp", "ICMP"))
        if target.tcp_port:
            kinds.append((f"tcp:{target.tcp_port}", f"TCP:{target.tcp_port}"))

        for kind_key, kind_label in kinds:
            stats = app.monitor.stats.get((target.name, kind_key))
            if stats is None:
                continue
            snap = stats.snapshot()
            stats_keys = ("total", "success", "loss_pct", "recent_loss_pct",
                          "avg", "min", "max", "jitter", "last",
                          "consecutive_fail", "consecutive_ok")
            targets_out.append({
                "name": target.name,
                "host": target.host,
                "group": target.group,
                "kind": kind_key,
                "kind_label": kind_label,
                "status": _classify_target(snap),
                "stats": {k: snap[k] for k in stats_keys},
                "samples": [
                    {"ok": bool(ok), "latency": lat, "ts": ts}
                    for ok, lat, ts in snap["samples"]
                ],
            })
            groups.setdefault(target.group, []).append(snap)

    return {
        "uptime_seconds": int(time.time() - app.start_time),
        "server_time": time.time(),
        "targets": targets_out,
        "groups": {g: _classify_group(s) for g, s in groups.items()},
    }


def _make_handler(app: AppState):
    static_root = STATIC_DIR.resolve()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):  # noqa: A002 - stdlib signature
            return

        def _send_json(self, code: int, data) -> None:
            body = json.dumps(data).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_file(self, path: Path) -> None:
            try:
                data = path.read_bytes()
            except OSError:
                self.send_error(404)
                return
            ctype, _ = mimetypes.guess_type(str(path))
            self.send_response(200)
            self.send_header("Content-Type", ctype or "application/octet-stream")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            parsed = urlparse(self.path)
            path = parsed.path

            if path in ("/", "/index.html"):
                self._send_file(STATIC_DIR / "index.html")
                return

            if path == "/api/status":
                self._send_json(200, build_status(app))
                return

            if path == "/api/config":
                self._send_json(200, asdict(app.config))
                return

            if path == "/api/events":
                q = parse_qs(parsed.query)
                try:
                    since = int(q.get("since", ["0"])[0])
                except (ValueError, IndexError):
                    since = 0
                self._send_json(200, {
                    "events": app.event_log.since(since),
                    "latest_seq": app.event_log.latest_seq(),
                })
                return

            if path == "/api/netinfo":
                from netinfo import get_network_info
                q = parse_qs(parsed.query)
                force = q.get("refresh", ["0"])[0] in ("1", "true", "yes")
                self._send_json(200, get_network_info(force_refresh=force))
                return

            if path == "/api/setup/suggest":
                from netinfo import get_network_info
                info = get_network_info()
                active = info.get("active") or {}
                dns_list = active.get("dns_servers") or []
                gateway = active.get("gateway") or ""
                self._send_json(200, {
                    "router_ip": gateway,
                    "isp1_gateway": gateway,
                    "dns_server": dns_list[0] if dns_list else "",
                    "upstream_host": "8.8.8.8",
                    "source_interface": active.get("name") or "",
                })
                return

            if path == "/api/events/export":
                body = format_log(app.event_log.all()).encode("utf-8")
                filename = f"fts-netmon-{time.strftime('%Y%m%d-%H%M%S')}.log"
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Content-Disposition",
                                 f'attachment; filename="{filename}"')
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return

            if path.startswith("/static/"):
                rel = path[len("/static/"):]
                candidate = (STATIC_DIR / rel).resolve()
                try:
                    candidate.relative_to(static_root)
                except ValueError:
                    self.send_error(403)
                    return
                self._send_file(candidate)
                return

            self.send_error(404)

        def do_POST(self):
            parsed = urlparse(self.path)
            path = parsed.path

            if path == "/api/config":
                try:
                    length = int(self.headers.get("Content-Length", 0))
                except ValueError:
                    length = 0
                if length <= 0 or length > 100_000:
                    self._send_json(400, {"error": "invalid content length"})
                    return
                body = self.rfile.read(length)
                try:
                    data = json.loads(body)
                except json.JSONDecodeError as e:
                    self._send_json(400, {"error": f"invalid JSON: {e}"})
                    return
                if not isinstance(data, dict):
                    self._send_json(400, {"error": "expected JSON object"})
                    return
                try:
                    app.update_config(data)
                except ValueError as e:
                    self._send_json(400, {"error": str(e)})
                    return
                self._send_json(200, {"ok": True, "config": asdict(app.config)})
                return

            self.send_error(404)

    return Handler


class WebServer:
    def __init__(self, app: AppState, host: str = "127.0.0.1", port: int = 8765):
        self.app = app
        self.host = host
        self.port = port
        self.server: ThreadingHTTPServer | None = None
        self.thread: Thread | None = None

    def start(self) -> None:
        handler = _make_handler(self.app)
        self.server = ThreadingHTTPServer((self.host, self.port), handler)
        self.thread = Thread(target=self.server.serve_forever, daemon=True,
                             name="fts-netmon-web")
        self.thread.start()

    def stop(self) -> None:
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()
            self.server = None
