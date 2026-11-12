#!/usr/bin/env python3
"""Working table and before/after diff for sonos-analyzer JSON reports. Read-only, stdlib only.

    sonos_table.py scan.json                 CSV working table, with blank columns for the
                                             network controller's view of each speaker
    sonos_table.py before.json after.json    what changed between two scans

Speaker-supplied text (room names, models) is printed as data: control characters are
stripped and anything a spreadsheet would run as a formula is quoted.
"""

from __future__ import annotations

import csv
import json
import re
import sys

SPEAKER_COLUMNS = [
    "room_name", "role", "bond", "model_name", "ip_address", "mac_address", "network_path",
    "radio_use", "wifi_band", "wifi_channel", "phy_errors_per_sec", "noise_floor_dbm",
    "ethernet_speed", "eth0_rx_errors", "stp_enabled", "br0_rx_drop_ratio_pct",
    "software_version", "boot_seq", "airplay_enabled",
]
# Filled in by hand from the network controller (UniFi client list, switch Port Manager).
CONTROLLER_COLUMNS = [
    "ap_or_switch_port", "band_channel_width", "signal_dbm", "tx_retry_pct",
    "last_roam_or_uptime", "port_speed_stp_errors", "fixed_ip", "agrees(Y/N/na)",
]


def clean(value) -> str:
    text = re.sub(r"[\x00-\x1f\x7f]", " ", "" if value is None else str(value))[:60]
    if isinstance(value, str) and text[:1] in ("=", "+", "-", "@"):
        return "'" + text
    return text


def load(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def speaker_key(sp: dict) -> tuple:
    """Stable across IP changes: room plus role."""
    return (sp.get("room_id") or sp.get("ip_address"), sp.get("role") or "")


def radio_use(report: dict) -> dict[str, str]:
    return {s["ip"]: row["use"] for row in report.get("wireless", []) for s in row["speakers"]}


def table(report: dict) -> None:
    use = radio_use(report)
    out = csv.writer(sys.stdout)
    out.writerow(SPEAKER_COLUMNS + CONTROLLER_COLUMNS)
    for sp in report["speakers"]:
        row = dict(sp, radio_use=use.get(sp["ip_address"], ""))
        out.writerow([clean(row.get(c)) for c in SPEAKER_COLUMNS] + [""] * len(CONTROLLER_COLUMNS))
    print(
        f"# {report['speaker_count']} speakers / {report['room_count']} rooms, "
        f"generated {clean(report['generated_at'])}, "
        f"mesh_active={report.get('connections', {}).get('mesh_active')}, "
        f"fetch_errors={len(report.get('fetch_errors', []))}"
    )


def finding_key(f: dict) -> tuple:
    return (f["category"], f["severity"], re.sub(r"\d+", "#", f["title"]))


def counter_delta(x: dict, y: dict, packets: str, bad: str) -> tuple[int, int] | None:
    """Change in a lifetime counter between scans, or None if the speaker rebooted."""
    if x.get("boot_seq") != y.get("boot_seq") or packets not in x or packets not in y:
        return None
    return y[packets] - x[packets], y.get(bad, 0) - x.get(bad, 0)


def diff(a: dict, b: dict) -> None:
    sa = {speaker_key(s): s for s in a["speakers"]}
    sb = {speaker_key(s): s for s in b["speakers"]}
    ua, ub = radio_use(a), radio_use(b)
    for k in sa.keys() - sb.keys():
        print(f"GONE     {clean(sa[k]['room_name'])} {clean(sa[k]['role'])} ({sa[k]['ip_address']})")
    for k in sb.keys() - sa.keys():
        print(f"NEW      {clean(sb[k]['room_name'])} {clean(sb[k]['role'])} ({sb[k]['ip_address']})")
    for k in sorted(sa.keys() & sb.keys(), key=str):
        x, y = sa[k], sb[k]
        name = f"{clean(x['room_name'])} {clean(x['role'])}".strip()
        notes = []
        for f in ("ip_address", "network_path", "wifi_band", "wifi_channel", "ethernet_speed",
                  "software_version", "boot_seq", "noise_floor_dbm", "stp_enabled"):
            if x.get(f) != y.get(f):
                notes.append(f"{f}: {clean(x.get(f))} -> {clean(y.get(f))}")
        if ua.get(x["ip_address"]) != ub.get(y["ip_address"]):
            notes.append(f"radio_use: {ua.get(x['ip_address'])} -> {ub.get(y['ip_address'])}")
        rx, ry = x.get("phy_errors_per_sec"), y.get("phy_errors_per_sec")
        if rx is not None and ry is not None and max(rx, ry) >= 100 and (ry > 2 * rx or rx > 2 * ry):
            notes.append(f"phy_errors_per_sec: {rx:,.0f} -> {ry:,.0f}")
        drops = counter_delta(x, y, "br0_rx_packets", "br0_rx_dropped")
        if drops and drops[0] > 1000:
            notes.append(
                f"rx_drop over interval: {100 * drops[1] / drops[0]:.1f}% of {drops[0]:,} pkts "
                f"(lifetime {y.get('br0_rx_drop_ratio_pct')}%)"
            )
        errors = counter_delta(x, y, "eth0_rx_packets", "eth0_rx_errors")
        if errors and errors[1] > 0:
            notes.append(f"eth0 rx errors over interval: {errors[1]:,} in {errors[0]:,} pkts")
        if notes:
            print(f"CHANGED  {name}: " + "; ".join(notes))

    fa = {finding_key(f): f for f in a["findings"]}
    fb = {finding_key(f): f for f in b["findings"]}
    for k in fa.keys() - fb.keys():
        if k[1] != "ok":
            print(f"CLEARED  [{k[1]}] {clean(fa[k]['title'])}")
    for k in fb.keys() - fa.keys():
        if k[1] != "ok":
            print(f"APPEARED [{k[1]}] {clean(fb[k]['title'])}")
    for k in fa.keys() & fb.keys():
        if k[1] in ("high", "medium", "low"):
            same = set(fa[k]["affected_ips"]) == set(fb[k]["affected_ips"])
            tag = "PERSISTS" if same else "PERSISTS (affected set changed)"
            print(f"{tag} [{k[1]}] {clean(fb[k]['title'])}")
    print(
        f"# speakers {a['speaker_count']} -> {b['speaker_count']}; "
        f"fetch_errors {len(a.get('fetch_errors', []))} -> {len(b.get('fetch_errors', []))}"
    )


def main(argv: list[str]) -> int:
    if len(argv) == 1:
        table(load(argv[0]))
    elif len(argv) == 2:
        diff(load(argv[0]), load(argv[1]))
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
