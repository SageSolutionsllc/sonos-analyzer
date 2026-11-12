"""Command-line interface for sonos-analyzer."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from sonos_analyzer.analyze import analyze
from sonos_analyzer.collect import collect_snapshot
from sonos_analyzer.discovery import discover_speakers, off_network_hint
from sonos_analyzer.report import print_terminal, write_html, write_json


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Analyze Sonos speakers on your local network.",
        epilog="""Examples:
  sonos-analyzer
  sonos-analyzer --ips 192.168.1.165,192.168.1.89
  sonos-analyzer --json report.json --html report.html
""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--ips",
        help="Comma-separated speaker IPs (skip SSDP discovery)",
    )
    parser.add_argument(
        "--discover-timeout",
        type=float,
        default=3.0,
        help="SSDP discovery timeout in seconds (default: 3)",
    )
    parser.add_argument(
        "--interface",
        default=os.environ.get("SONOS_ANALYZER_INTERFACE") or None,
        help="Limit discovery to one interface, by name or IPv4 address (default: $SONOS_ANALYZER_INTERFACE, else all interfaces)",
    )
    parser.add_argument(
        "--phy-sample",
        type=float,
        default=5.0,
        metavar="SECONDS",
        help="Length of each of the 3 windows used to measure Wi-Fi PHY error rates; 0 to skip (default: 5)",
    )
    parser.add_argument(
        "--json",
        metavar="PATH",
        help="Write JSON report to PATH",
    )
    parser.add_argument(
        "--html",
        metavar="PATH",
        help="Write HTML report to PATH",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress terminal report (useful with --json/--html only)",
    )

    args = parser.parse_args(argv)

    if args.ips:
        ips = [ip.strip() for ip in args.ips.split(",") if ip.strip()]
    else:
        discovered = discover_speakers(timeout=args.discover_timeout, interface=args.interface)
        ips = [d.ip for d in discovered]
        if not ips:
            print(
                "No Sonos speakers discovered via SSDP. "
                "Try --ips 192.168.1.x or open a speaker's IP in a browser to confirm it is reachable.",
                file=sys.stderr,
            )
            return 1

    snapshot = collect_snapshot(ips, phy_sample_seconds=args.phy_sample)
    if not snapshot.speakers:
        print("Could not read diagnostics from any speaker.", file=sys.stderr)
        if hint := off_network_hint(ips):
            print(hint, file=sys.stderr)
        for err in snapshot.fetch_errors:
            print(f"  {err}", file=sys.stderr)
        return 1

    report = analyze(snapshot)

    if not args.quiet:
        print_terminal(report)

    if args.json:
        write_json(report, Path(args.json))
        if not args.quiet:
            print(f"Wrote JSON report to {args.json}")

    if args.html:
        write_html(report, Path(args.html))
        if not args.quiet:
            print(f"Wrote HTML report to {args.html}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
