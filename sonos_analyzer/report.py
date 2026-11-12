"""Render analysis reports to terminal, JSON, and HTML."""

from __future__ import annotations

import json
from dataclasses import asdict
from html import escape
from pathlib import Path

from sonos_analyzer.analyze import AnalysisReport, Finding


FIRMWARE_STATUS = {
    "newest": "Newest in household",
    "behind": "Update available",
    "older_line": "Older release line",
}

SEVERITY_LABEL = {
    "high": "HIGH",
    "medium": "MEDIUM",
    "low": "LOW",
    "info": "INFO",
    "ok": "OK",
}


def print_terminal(report: AnalysisReport) -> None:
    print(f"Sonos household analysis ({report.speaker_count} speaker(s))")
    print(f"Generated: {report.generated_at}")
    print()

    print(f"Speakers ({report.room_count} room(s))")
    print("-" * 72)
    for sp in report.speakers:
        name = sp["room_name"] if not sp["role"] else f"  {sp['role']}" if _is_secondary(sp) else f"{sp['room_name']} / {sp['role']}"
        rate = sp["phy_errors_per_sec"]
        rate_text = f", {rate:,.0f} PHY err/s" if rate is not None else ""
        print(
            f"  {name:<26} {sp['ip_address']:<16} {sp['model_name'] or '':<24} "
            f"{sp['connection_summary']}{rate_text}"
        )
    print()

    print("Firmware")
    print("-" * 72)
    for group in report.firmware:
        note = {"behind": " - update available", "older_line": " - older release line"}.get(group["status"], "")
        print(f"  {group['version']:<14} {group['count']:>2} speaker(s): {', '.join(group['models'])}{note}")
    print()

    print("Radio channels")
    print("-" * 72)
    for row in report.wireless:
        where = f"{row['band']} ch {row['channel']}" if row["channel"] else "-"
        print(f"  {row['label']:<28} {where:<14} {', '.join(s['name'] for s in row['speakers'])}")
    print()

    print("Findings")
    print("-" * 72)
    for finding in report.findings:
        confidence = f" ({finding.confidence} confidence)" if finding.confidence != "high" else ""
        print(f"[{SEVERITY_LABEL.get(finding.severity, finding.severity.upper())}] {finding.title}{confidence}")
        print(f"  {finding.detail}")
        for item in finding.affected:
            note = f": {item['note']}" if item["note"] else ""
            print(f"    - {item['name']} ({item['ip']}){note}")
        print()

    print("Recommendations")
    print("-" * 72)
    for idx, rec in enumerate(report.recommendations, start=1):
        print(f"  {idx}. {rec}")
    print()


def report_payload(report: AnalysisReport) -> dict:
    return {
        "generated_at": report.generated_at,
        "speaker_count": report.speaker_count,
        "room_count": report.room_count,
        "firmware_versions": report.firmware_versions,
        "firmware": report.firmware,
        "wireless": report.wireless,
        "connections": report.connections,
        "speakers": report.speakers,
        "findings": [asdict(f) for f in report.findings],
        "recommendations": report.recommendations,
        "source_ips": report.snapshot.source_ips,
        "fetch_errors": report.snapshot.fetch_errors,
    }


def _is_secondary(sp: dict) -> bool:
    """Bonded speaker other than the room's first (Front / Left)."""
    return bool(sp["role"]) and sp["role"] not in {"Front", "Left"}


def write_json(report: AnalysisReport, path: Path) -> None:
    path.write_text(json.dumps(report_payload(report), indent=2), encoding="utf-8")


def write_html(report: AnalysisReport, path: Path) -> None:
    path.write_text(render_html(report), encoding="utf-8")


def render_html(report: AnalysisReport) -> str:
    speaker_rows = "".join(_html_speaker_row(sp) for sp in report.speakers)
    finding_blocks = "".join(_html_finding(f) for f in report.findings)
    firmware_rows = "".join(
        "<tr>"
        f"<td>{escape(g['version'])}</td><td>{g['count']}</td>"
        f"<td>{escape(', '.join(g['models']))}</td>"
        f"<td>{escape(FIRMWARE_STATUS.get(g['status'], g['status']))}</td>"
        "</tr>"
        for g in report.firmware
    )
    wireless_rows = "".join(
        "<tr>"
        f"<td>{escape(w['label'])}</td><td>{escape(w['band'])}</td>"
        f"<td>{w['channel'] or ''}</td>"
        f"<td>{escape(', '.join(s['name'] for s in w['speakers']))}</td>"
        "</tr>"
        for w in report.wireless
    )
    rec_items = "".join(f"<li>{escape(rec)}</li>" for rec in report.recommendations)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Sonos household analysis</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 2rem; color: #111; background: #fafafa; }}
    h1, h2 {{ margin-bottom: 0.4rem; }}
    .meta {{ color: #555; margin-bottom: 1.5rem; }}
    table {{ border-collapse: collapse; width: 100%; background: #fff; margin: 1rem 0; }}
    th, td {{ border: 1px solid #ddd; padding: 0.5rem 0.75rem; text-align: left; vertical-align: top; }}
    th {{ background: #f0f0f0; }}
    .finding {{ background: #fff; border: 1px solid #ddd; border-left-width: 4px; padding: 1rem; margin: 0.75rem 0; }}
    .high {{ border-left-color: #c0392b; }}
    .medium {{ border-left-color: #d68910; }}
    .low {{ border-left-color: #2980b9; }}
    .info {{ border-left-color: #7f8c8d; }}
    .ok {{ border-left-color: #27ae60; }}
    ul {{ line-height: 1.5; }}
  </style>
</head>
<body>
  <h1>Sonos household analysis</h1>
  <p class="meta">{report.speaker_count} speaker(s) in {report.room_count} room(s) · Generated {escape(report.generated_at)}</p>

  <h2>Speakers</h2>
  <table>
    <thead>
      <tr>
        <th>Room</th><th>Role</th><th>IP</th><th>Model</th><th>Connection</th><th>Firmware</th><th>PHY errors/s</th><th>RX drop %</th>
      </tr>
    </thead>
    <tbody>{speaker_rows}</tbody>
  </table>

  <h2>Firmware</h2>
  <table>
    <thead><tr><th>Version</th><th>Speakers</th><th>Models</th><th>Status</th></tr></thead>
    <tbody>{firmware_rows}</tbody>
  </table>

  <h2>Radio channels</h2>
  <table>
    <thead><tr><th>Use</th><th>Band</th><th>Channel</th><th>Speakers</th></tr></thead>
    <tbody>{wireless_rows}</tbody>
  </table>

  <h2>Speaker-to-speaker signal</h2>
  {_html_signal_matrix(report.connections)}

  <h2>Findings</h2>
  {finding_blocks or '<p>No findings.</p>'}

  <h2>Recommendations</h2>
  <ul>{rec_items}</ul>
</body>
</html>
"""


def _html_signal_matrix(connections: dict) -> str:
    nodes = connections.get("nodes", [])
    if len(nodes) < 2:
        return "<p>No speaker-to-speaker signal data reported.</p>"
    strength = {}
    for link in connections["links"]:
        strength[(link["a"], link["b"])] = strength[(link["b"], link["a"])] = link["strength"]
    header = "".join(f"<th>{escape(n['name'])}</th>" for n in nodes)
    rows = "".join(
        f"<tr><th>{escape(row['name'])}</th>"
        + "".join(
            f"<td>{'' if row is col else strength.get((row['ip'], col['ip'])) or '-'}</td>"
            for col in nodes
        )
        + "</tr>"
        for row in nodes
    )
    return (
        "<p>Average signal between each pair of speaker radios "
        "(45+ strong, 30-44 fair, 18-29 weak, under 18 poor, - not heard).</p>"
        f"<table><thead><tr><th></th>{header}</tr></thead><tbody>{rows}</tbody></table>"
    )


def _html_speaker_row(sp: dict) -> str:
    rate = sp["phy_errors_per_sec"]
    drop = sp["br0_rx_drop_ratio_pct"]
    return (
        "<tr>"
        f"<td>{escape('' if _is_secondary(sp) else sp['room_name'] or '')}</td>"
        f"<td>{escape(sp['role'] or '')}</td>"
        f"<td>{escape(sp['ip_address'] or '')}</td>"
        f"<td>{escape(sp['model_name'] or '')}</td>"
        f"<td>{escape(sp['connection_summary'] or '')}</td>"
        f"<td>{escape(sp['software_version'] or '')}</td>"
        f"<td>{f'{rate:,.0f}' if rate is not None else ''}</td>"
        f"<td>{drop if drop is not None else ''}</td>"
        "</tr>"
    )


def _html_finding(finding: Finding) -> str:
    items = "".join(
        f"<li>{escape(item['name'])} ({escape(item['ip'])})"
        f"{': ' + escape(item['note']) if item['note'] else ''}</li>"
        for item in finding.affected
    )
    return (
        f'<div class="finding {escape(finding.severity)}">'
        f"<h3>{escape(finding.title)}</h3>"
        + (f'<p class="muted">{escape(finding.confidence)} confidence - confirm before acting</p>'
           if finding.confidence != "high" else "")
        + f"<p>{escape(finding.detail)}</p>"
        f"{f'<ul>{items}</ul>' if items else ''}</div>"
    )
