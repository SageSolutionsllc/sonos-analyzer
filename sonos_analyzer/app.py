"""Desktop app entry point: serve the web UI on this computer and open the browser."""

from __future__ import annotations

import argparse
import socket
import sys
import threading
import time
import webbrowser
from http.server import ThreadingHTTPServer

from sonos_analyzer import __version__, web


FIRST_PORT = 8400
PORTS_TO_TRY = 20
# Stop on our own when no browser tab has been open for this long.
IDLE_TIMEOUT_SECONDS = 15 * 60


def _bind(port: int | None) -> ThreadingHTTPServer:
    candidates = [port] if port else range(FIRST_PORT, FIRST_PORT + PORTS_TO_TRY)
    error: OSError | None = None
    for candidate in candidates:
        try:
            return ThreadingHTTPServer(("127.0.0.1", candidate), web.Handler)
        except OSError as exc:
            error = exc
    raise SystemExit(f"Could not open a local port for the web page: {error}")


def _stop_when_idle(server: ThreadingHTTPServer, timeout: float) -> None:
    while True:
        time.sleep(30)
        if time.monotonic() - web.last_activity > timeout:
            print("No browser tab open for a while; stopping.", flush=True)
            server.shutdown()
            return


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Sonos Analyzer on this computer and open it in the browser.")
    parser.add_argument("--port", type=int, help=f"Port for the web page (default: first free from {FIRST_PORT})")
    parser.add_argument("--no-browser", action="store_true", help="Do not open the browser")
    parser.add_argument(
        "--idle-timeout",
        type=float,
        default=IDLE_TIMEOUT_SECONDS,
        help="Stop after this many seconds without the page open; 0 to never stop (default: 900)",
    )
    args = parser.parse_args(argv)

    server = _bind(args.port)
    url = f"http://127.0.0.1:{server.server_address[1]}/"

    web.APP_MODE = True
    web.on_quit = server.shutdown
    web.last_activity = time.monotonic()
    if args.idle_timeout > 0:
        threading.Thread(target=_stop_when_idle, args=(server, args.idle_timeout), daemon=True).start()

    print(f"Sonos Analyzer {__version__} is running at {url}", flush=True)
    print("It only reads from your speakers; nothing on them is changed.", flush=True)
    print("To stop it, use Quit on the page or close this window.", flush=True)
    if not args.no_browser:
        threading.Timer(0.5, webbrowser.open, args=(url,)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
