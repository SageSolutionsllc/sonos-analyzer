"""Collect diagnostics from the speakers into a HouseholdSnapshot."""

from __future__ import annotations

import re
import statistics
import time
from concurrent.futures import ThreadPoolExecutor

from sonos_analyzer.fetch import (
    fetch_ath_status,
    fetch_device_description,
    fetch_review,
    fetch_zone_group_state,
    is_reachable,
)
from sonos_analyzer.parse import (
    HouseholdSnapshot,
    merge_speakers,
    parse_device_description,
    parse_review_xml,
    parse_zone_group_state,
)


MAX_WORKERS = 12
# The PHY error rate is measured over this many back-to-back windows of --phy-sample seconds.
PHY_WINDOWS = 3
PHY_ERRORS_RE = re.compile(r"PHY errors since last reading/reset:\s*(\d+)")


def collect_snapshot(ips: list[str], phy_sample_seconds: float = 5.0) -> HouseholdSnapshot:
    """Read diagnostics starting from the given speaker IPs.

    phy_sample_seconds: window used to measure each radio's PHY error rate
    (0 skips the measurement).
    """
    snapshot = HouseholdSnapshot(source_ips=ips)
    review_maps = []
    covered: set[str] = set()
    reachable: list[str] = []

    # One speaker's review covers the whole household, so only ask speakers
    # that no earlier answer has described yet.
    # Rule out unreachable speakers together, instead of waiting on each in turn.
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        up = dict(zip(ips, pool.map(is_reachable, ips)))

    for ip in ips:
        if ip in covered:
            continue
        if not up[ip]:
            snapshot.fetch_errors.append(f"{ip}: no response on port 1400")
            continue
        try:
            review = parse_review_xml(fetch_review(ip))
        except Exception as exc:  # noqa: BLE001 - surface as non-fatal
            snapshot.fetch_errors.append(f"{ip}: {exc}")
            continue
        review_maps.append(review)
        covered.update(review)
        reachable.append(ip)

    group_maps = []
    group_errors = []
    for ip in reachable:
        try:
            group_maps.append(parse_zone_group_state(fetch_zone_group_state(ip)))
            break
        except Exception as exc:  # noqa: BLE001 - surface as non-fatal
            group_errors.append(f"{ip} zone group: {exc}")
    if not group_maps:
        snapshot.fetch_errors.extend(group_errors)

    snapshot.speakers = merge_speakers(*review_maps, *group_maps)
    if not snapshot.speakers:
        return snapshot

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        _add_device_descriptions(snapshot, pool)
        if phy_sample_seconds > 0:
            _sample_phy_error_rates(snapshot, pool, phy_sample_seconds)

    return snapshot


def _add_device_descriptions(snapshot: HouseholdSnapshot, pool: ThreadPoolExecutor) -> None:
    def describe(ip: str) -> dict[str, str] | str:
        try:
            return parse_device_description(fetch_device_description(ip))
        except Exception as exc:  # noqa: BLE001 - surface as non-fatal
            return f"{ip} description: {exc}"

    ips = list(snapshot.speakers)
    for ip, meta in zip(ips, pool.map(describe, ips)):
        if isinstance(meta, str):
            snapshot.fetch_errors.append(meta)
            continue
        speaker = snapshot.speakers[ip]
        speaker.model_name = meta.get("model_name", speaker.model_name)
        speaker.model_number = meta.get("model_number", speaker.model_number)
        speaker.display_version = meta.get("display_version", speaker.display_version)


def _sample_phy_error_rates(snapshot: HouseholdSnapshot, pool: ThreadPoolExecutor, seconds: float) -> None:
    """The PHY error counter resets on every read, so read twice and divide."""

    def read(ip: str) -> tuple[float, int] | None:
        try:
            match = PHY_ERRORS_RE.search(fetch_ath_status(ip))
        except Exception:  # noqa: BLE001 - rate is optional
            return None
        return (time.monotonic(), int(match.group(1))) if match else None

    ips = [ip for ip, sp in snapshot.speakers.items() if sp.phy_errors is not None]
    previous = list(pool.map(read, ips))
    # Several windows, so one burst (a microwave, a neighbour) is not reported as a problem.
    for _ in range(PHY_WINDOWS):
        time.sleep(seconds)
        current = list(pool.map(read, ips))
        for ip, first, second in zip(ips, previous, current):
            if first and second and second[0] > first[0]:
                snapshot.speakers[ip].phy_error_rates.append(second[1] / (second[0] - first[0]))
        previous = current
    for ip in ips:
        rates = snapshot.speakers[ip].phy_error_rates
        if rates:
            snapshot.speakers[ip].phy_error_rate = statistics.median(rates)
