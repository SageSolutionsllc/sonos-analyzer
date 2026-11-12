"""Web front end for sonos-analyzer (stdlib only)."""

from __future__ import annotations

import argparse
import ipaddress
import json
import os
import signal
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources

from sonos_analyzer import __version__
from sonos_analyzer.analyze import AnalysisReport, analyze
from sonos_analyzer.collect import collect_snapshot
from sonos_analyzer.discovery import discover_speakers, off_network_hint
from sonos_analyzer.report import render_html, report_payload


MAX_BODY = 16 * 1024
MAX_IPS = 64
MAX_DISCOVER_TIMEOUT = 15.0

DISCOVERY_INTERFACE = os.environ.get("SONOS_ANALYZER_INTERFACE") or None

_scan_lock = threading.Lock()
_last_report: AnalysisReport | None = None


class ScanError(Exception):
    def __init__(self, status: HTTPStatus, message: str, fetch_errors: list[str] | None = None):
        super().__init__(message)
        self.status = status
        self.message = message
        self.fetch_errors = fetch_errors or []


def parse_ips(raw: object) -> list[str]:
    """Validate user-supplied speaker addresses; only private LAN IPs are probed."""
    if raw in (None, "", []):
        return []
    if isinstance(raw, str):
        raw = raw.replace(",", " ").split()
    if not isinstance(raw, list):
        raise ScanError(HTTPStatus.BAD_REQUEST, "ips must be a list or comma-separated string")
    if len(raw) > MAX_IPS:
        raise ScanError(HTTPStatus.BAD_REQUEST, f"Too many IPs (max {MAX_IPS})")

    ips: list[str] = []
    for item in raw:
        try:
            addr = ipaddress.ip_address(str(item).strip())
        except ValueError:
            raise ScanError(HTTPStatus.BAD_REQUEST, f"Not a valid IP address: {item}") from None
        if addr.version != 4 or not addr.is_private:
            raise ScanError(HTTPStatus.BAD_REQUEST, f"Not a private IPv4 address: {item}")
        if str(addr) not in ips:
            ips.append(str(addr))
    return ips


def run_scan(ips: list[str], discover_timeout: float) -> AnalysisReport:
    global _last_report

    if not _scan_lock.acquire(blocking=False):
        raise ScanError(HTTPStatus.CONFLICT, "A scan is already running. Try again in a moment.")
    try:
        if not ips:
            try:
                found = discover_speakers(timeout=discover_timeout, interface=DISCOVERY_INTERFACE)
            except OSError as exc:
                raise ScanError(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    f"Discovery failed on interface {DISCOVERY_INTERFACE or 'all'}: {exc}",
                ) from None
            ips = [d.ip for d in found]
            if not ips:
                raise ScanError(
                    HTTPStatus.NOT_FOUND,
                    "No Sonos speakers discovered via SSDP. Enter speaker IPs manually, "
                    "and check the container is running with host networking.",
                )

        snapshot = collect_snapshot(ips)
        if not snapshot.speakers:
            hint = off_network_hint(ips)
            raise ScanError(
                HTTPStatus.BAD_GATEWAY,
                "Could not read diagnostics from any speaker." + (f" {hint}" if hint else ""),
                snapshot.fetch_errors,
            )

        _last_report = analyze(snapshot)
        return _last_report
    finally:
        _scan_lock.release()


class Handler(BaseHTTPRequestHandler):
    server_version = f"sonos-analyzer/{__version__}"

    def do_GET(self) -> None:  # noqa: N802 - http.server naming
        path = self.path.split("?", 1)[0]
        if path in ("/", "/index.html"):
            page = resources.files("sonos_analyzer").joinpath("static/index.html").read_bytes()
            self._send(HTTPStatus.OK, page, "text/html; charset=utf-8")
        elif path == "/healthz":
            self._send_json(HTTPStatus.OK, {"status": "ok", "version": __version__})
        elif path == "/api/report":
            if _last_report is None:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "No scan has been run yet."})
            else:
                self._send_json(HTTPStatus.OK, report_payload(_last_report))
        elif path == "/report.html":
            if _last_report is None:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "No scan has been run yet."})
            else:
                self._send(
                    HTTPStatus.OK,
                    render_html(_last_report).encode("utf-8"),
                    "text/html; charset=utf-8",
                    {"Content-Disposition": 'attachment; filename="sonos-report.html"'},
                )
        else:
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})

    def do_POST(self) -> None:  # noqa: N802 - http.server naming
        if self.path.split("?", 1)[0] != "/api/analyze":
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})
            return

        # Requiring JSON forces a CORS preflight, so other sites cannot trigger scans.
        if self.headers.get_content_type() != "application/json":
            self._send_json(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, {"error": "Content-Type must be application/json"})
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length > MAX_BODY:
                raise ScanError(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "Request body too large")
            try:
                body = json.loads(self.rfile.read(length) or b"{}")
            except ValueError:
                raise ScanError(HTTPStatus.BAD_REQUEST, "Request body is not valid JSON") from None
            if not isinstance(body, dict):
                raise ScanError(HTTPStatus.BAD_REQUEST, "Request body must be a JSON object")

            ips = parse_ips(body.get("ips"))
            try:
                timeout = float(body.get("discover_timeout", 3.0))
            except (TypeError, ValueError):
                raise ScanError(HTTPStatus.BAD_REQUEST, "discover_timeout must be a number") from None
            timeout = min(max(timeout, 1.0), MAX_DISCOVER_TIMEOUT)

            report = run_scan(ips, timeout)
        except ScanError as exc:
            self._send_json(exc.status, {"error": exc.message, "fetch_errors": exc.fetch_errors})
            return
        except Exception as exc:  # noqa: BLE001 - report instead of dropping the connection
            self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": f"Scan failed: {exc}"})
            return

        self._send_json(HTTPStatus.OK, report_payload(report))

    def _send_json(self, status: HTTPStatus, payload: dict) -> None:
        self._send(status, json.dumps(payload).encode("utf-8"), "application/json")

    def _send(
        self,
        status: HTTPStatus,
        body: bytes,
        content_type: str,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        for key, value in (extra_headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)


def _raise_interrupt(_signum: int, _frame: object) -> None:
    raise KeyboardInterrupt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Serve the sonos-analyzer web UI.")
    parser.add_argument(
        "--host",
        default=os.environ.get("SONOS_ANALYZER_HOST", "127.0.0.1"),
        help="Address to bind (default: 127.0.0.1, or $SONOS_ANALYZER_HOST)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("SONOS_ANALYZER_PORT", "8400")),
        help="Port to listen on (default: 8400, or $SONOS_ANALYZER_PORT)",
    )
    args = parser.parse_args(argv)

    # As PID 1 in a container Python ignores SIGTERM unless a handler is installed.
    signal.signal(signal.SIGTERM, _raise_interrupt)

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(
        f"sonos-analyzer web UI listening on http://{args.host}:{args.port} "
        f"(discovery interface: {DISCOVERY_INTERFACE or 'all'})",
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
