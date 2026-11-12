"""Parse Sonos diagnostic XML into structured data."""

from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field


@dataclass
class IfconfigStats:
    rx_packets: int = 0
    tx_packets: int = 0
    rx_dropped: int = 0
    tx_dropped: int = 0
    rx_errors: int = 0
    tx_errors: int = 0


@dataclass
class SpeakerDiagnostics:
    zone_name: str
    ip_address: str
    mac_address: str = ""
    serial_number: str = ""
    local_uid: str = ""
    model_name: str = ""
    model_number: str = ""
    software_version: str = ""
    display_version: str = ""
    hardware_version: str = ""
    connection_type: str = ""
    connection_type_code: str = ""
    wifi_mode: str = ""
    ethernet_link: bool = False
    ethernet_speed: str = ""
    wifi_channel_mhz: str = ""
    wifi_home_channel_mhz: str = ""
    behind_wifi_extender: bool = False
    room_calibration_state: str = ""
    boot_seq: str = ""
    airplay_enabled: bool = False
    is_invisible: bool = False
    channel_map_set: str = ""
    coordinator_uid: str = ""
    group_id: str = ""
    br0: IfconfigStats = field(default_factory=IfconfigStats)
    eth0: IfconfigStats = field(default_factory=IfconfigStats)
    phy_errors: int | None = None
    noise_floor_dbm: list[int] = field(default_factory=list)
    hal_reset_failures: int | None = None
    is_stereo_left: bool = False
    is_stereo_right: bool = False
    is_stereo_coordinator: bool = False
    # Room / bonded-set membership (from zone group topology)
    room_name: str = ""
    room_uid: str = ""
    role: str = ""
    bond: str = ""  # "stereo_pair", "home_theater" or ""
    ht_sat_chan_map_set: str = ""
    wifi_enabled: bool | None = None
    # Radio / bridge detail (from /support/review)
    radio_mode: str = ""
    ht_channel_mhz: str = ""
    rx_chains: int = 0
    sonosnet_disabled: bool | None = None
    stp_enabled: bool | None = None
    stp_is_root: bool = False
    stp_ports: list[tuple[str, str]] = field(default_factory=list)
    # Other radios this speaker hears: (mac, signal from, signal to, stp state)
    radio_peers: list[tuple[str, int, int, str]] = field(default_factory=list)
    # PHY errors per second, sampled over a short window by the collector
    phy_error_rate: float | None = None
    # One rate per sample window; a radio is only flagged if it stays high in all of them
    phy_error_rates: list[float] = field(default_factory=list)


@dataclass
class HouseholdSnapshot:
    speakers: dict[str, SpeakerDiagnostics] = field(default_factory=dict)
    source_ips: list[str] = field(default_factory=list)
    fetch_errors: list[str] = field(default_factory=list)


def parse_review_xml(xml_text: str) -> dict[str, SpeakerDiagnostics]:
    root = ET.fromstring(xml_text)
    speakers: dict[str, SpeakerDiagnostics] = {}

    for block in root.findall("ZPSupportInfo"):
        speaker = _parse_support_block(block)
        if speaker and speaker.ip_address:
            speakers[speaker.ip_address] = speaker

    return speakers


def parse_device_description(xml_text: str) -> dict[str, str]:
    root = ET.fromstring(xml_text)
    ns = {"d": "urn:schemas-upnp-org:device-1-0"}
    device = root.find("d:device", ns)
    if device is None:
        device = root.find("device")
    if device is None:
        return {}

    def text(tag: str) -> str:
        # Elements without children are falsy, so `or` cannot be used here.
        el = device.find(f"d:{tag}", ns)
        if el is None:
            el = device.find(tag)
        return (el.text or "").strip() if el is not None else ""

    return {
        "model_name": text("modelName"),
        "model_number": text("modelNumber"),
        "display_version": text("displayVersion"),
        "room_name": text("roomName"),
    }


def parse_zone_group_state(xml_text: str) -> dict[str, SpeakerDiagnostics]:
    """Parse escaped ZoneGroupState XML from SOAP response."""
    if not xml_text:
        return {}

    unescaped = html.unescape(xml_text.strip())
    root = ET.fromstring(unescaped)
    speakers: dict[str, SpeakerDiagnostics] = {}

    for group in root.findall(".//ZoneGroup"):
        coordinator = group.attrib.get("Coordinator", "")
        group_id = group.attrib.get("ID", "")

        for member in group.findall("ZoneGroupMember"):
            # Home theater surrounds and subs are nested under their primary.
            for element in [member, *member.findall("Satellite")]:
                speaker = _parse_zone_member(element, coordinator, group_id)
                if speaker:
                    speakers[speaker.ip_address] = speaker

    names_by_uid = {sp.local_uid: sp.zone_name for sp in speakers.values()}
    for speaker in speakers.values():
        speaker.room_name = names_by_uid.get(speaker.room_uid, speaker.zone_name)

    return speakers


def _parse_zone_member(member: ET.Element, coordinator: str, group_id: str) -> SpeakerDiagnostics | None:
    attrib = member.attrib
    ip = _ip_from_location(attrib.get("Location", ""))
    if not ip:
        return None

    uuid = attrib.get("UUID", "")
    channel_map = attrib.get("ChannelMapSet", "")
    ht_map = attrib.get("HTSatChanMapSet", "")
    speaker = SpeakerDiagnostics(
        zone_name=attrib.get("ZoneName", ip),
        ip_address=ip,
        local_uid=uuid,
        software_version=attrib.get("SoftwareVersion", ""),
        connection_type_code=attrib.get("ConnectionType", ""),
        wifi_channel_mhz=attrib.get("ChannelFreq", ""),
        behind_wifi_extender=attrib.get("BehindWifiExtender", "0") == "1",
        room_calibration_state=attrib.get("RoomCalibrationState", ""),
        boot_seq=attrib.get("BootSeq", ""),
        airplay_enabled=attrib.get("AirPlayEnabled", "0") == "1",
        is_invisible=attrib.get("Invisible", "0") == "1",
        channel_map_set=channel_map,
        ht_sat_chan_map_set=ht_map,
        coordinator_uid=coordinator,
        group_id=group_id,
        ethernet_link=attrib.get("EthLink", "0") == "1",
    )
    if "WifiEnabled" in attrib:
        speaker.wifi_enabled = attrib["WifiEnabled"] == "1"
    speaker.connection_type = _connection_type_label(speaker.connection_type_code)
    _apply_channel_map_roles(speaker, channel_map, coordinator, uuid)

    # The first entry of either map is the room's primary speaker.
    bond_map = ht_map or channel_map
    channels = _parse_channel_map(bond_map)
    speaker.room_uid = next(iter(channels), uuid)
    if uuid in channels:
        speaker.bond = "home_theater" if ht_map else "stereo_pair"
        speaker.role = _role_label(channels[uuid])
    return speaker


def _parse_channel_map(channel_map: str) -> dict[str, str]:
    """'UID:LF,LF;UID:RF,RF' -> {uid: channels}, in order."""
    channels: dict[str, str] = {}
    for part in channel_map.split(";"):
        if ":" in part:
            uid, chans = part.split(":", 1)
            channels[uid] = chans.upper()
    return channels


def _role_label(channels: str) -> str:
    first = channels.split(",")[0]
    if channels in {"LF,LF", "LF"}:
        return "Left"
    if channels in {"RF,RF", "RF"}:
        return "Right"
    if channels == "LF,RF":
        return "Front"
    if first == "SW":
        return "Sub"
    if first == "LR":
        return "Left surround"
    if first == "RR":
        return "Right surround"
    return channels


def merge_speakers(*maps: dict[str, SpeakerDiagnostics]) -> dict[str, SpeakerDiagnostics]:
    merged: dict[str, SpeakerDiagnostics] = {}
    for source in maps:
        for ip, speaker in source.items():
            if ip not in merged:
                merged[ip] = speaker
                continue
            existing = merged[ip]
            for key, value in speaker.__dict__.items():
                current = getattr(existing, key)
                if isinstance(current, IfconfigStats):
                    continue
                if current is None and value is not None:
                    # Tri-state fields (wifi_enabled, stp_enabled...): keep an explicit False.
                    setattr(existing, key, value)
                elif current in ("", 0, False, None, []) and value not in ("", 0, False, None, []):
                    setattr(existing, key, value)
    return merged


def _parse_support_block(block: ET.Element) -> SpeakerDiagnostics | None:
    zp = block.find("ZPInfo")
    if zp is None:
        return None

    def zp_text(tag: str) -> str:
        el = zp.find(tag)
        return (el.text or "").strip() if el is not None else ""

    speaker = SpeakerDiagnostics(
        zone_name=zp_text("ZoneName"),
        ip_address=zp_text("IPAddress"),
        mac_address=zp_text("MACAddress"),
        serial_number=zp_text("SerialNumber"),
        local_uid=zp_text("LocalUID"),
        software_version=zp_text("SoftwareVersion"),
        hardware_version=zp_text("HardwareVersion"),
    )

    wireless = block.find("Wireless/WirelessInfo")
    if wireless is not None:
        speaker.wifi_mode = _child_text(wireless, "WifiModeString")
        conn = _child_text(wireless, "ConnectionTypeString")
        if conn:
            speaker.connection_type = conn
        speaker.connection_type_code = _child_text(wireless, "ConnectionType")
        sonosnet_disabled = _child_text(wireless, "SonosNetDisabled")
        if sonosnet_disabled:
            speaker.sonosnet_disabled = sonosnet_disabled == "1"

    # Multi-port models list every port; report the one with a link.
    for enet in block.findall("EnetPorts/Port"):
        if _child_text(enet, "Link") == "1":
            speaker.ethernet_link = True
            speaker.ethernet_speed = _child_text(enet, "Speed")
            break

    for cmd in block.findall("Command"):
        if cmd.attrib.get("cmdline") == "/sbin/ifconfig" and cmd.text:
            _parse_ifconfig(cmd.text, speaker)
        elif "brctl showstp" in cmd.attrib.get("cmdline", "") and cmd.text:
            _parse_showstp(cmd.text, speaker)

    for file_el in block.findall("File"):
        if file_el.attrib.get("name") == "/proc/ath_rincon/status" and file_el.text:
            _parse_ath_status(file_el.text, speaker)

    return speaker


def _parse_ifconfig(text: str, speaker: SpeakerDiagnostics) -> None:
    current = None
    for line in text.splitlines():
        line = line.rstrip()
        if line and not line[0].isspace():
            # Every interface block starts in column 0. Keep only br0 and eth0, so a
            # later block (lo, ath0, wlan0...) cannot overwrite their counters.
            name = line.split()[0].rstrip(":")
            current = {"br0": speaker.br0, "eth0": speaker.eth0}.get(name)
            continue
        if current is None:
            continue
        if "RX packets:" in line:
            m = re.search(
                r"RX packets:(\d+) errors:(\d+) dropped:(\d+)",
                line,
            )
            if m:
                current.rx_packets = int(m.group(1))
                current.rx_errors = int(m.group(2))
                current.rx_dropped = int(m.group(3))
        elif "TX packets:" in line:
            m = re.search(
                r"TX packets:(\d+) errors:(\d+) dropped:(\d+)",
                line,
            )
            if m:
                current.tx_packets = int(m.group(1))
                current.tx_errors = int(m.group(2))
                current.tx_dropped = int(m.group(3))


def _parse_showstp(text: str, speaker: SpeakerDiagnostics) -> None:
    if "STP is disabled" in text:
        speaker.stp_enabled = False
        return

    bridge_id = re.search(r"bridge id\s+(\S+)", text)
    if not bridge_id:
        return
    speaker.stp_enabled = True
    root = re.search(r"designated root\s+(\S+)", text)
    speaker.stp_is_root = bool(root) and root.group(1) == bridge_id.group(1)

    port = None
    for line in text.splitlines():
        header = re.match(r"^(\S+) \(\d+\)", line)
        if header:
            port = header.group(1)
            continue
        state = re.search(r"\bstate\s+(\w+)", line)
        if port and state:
            speaker.stp_ports.append((port, state.group(1)))
            port = None


def _parse_ath_status(text: str, speaker: SpeakerDiagnostics) -> None:
    mode_match = re.search(r"Mode: \w+ \((\w+)\)", text)
    if mode_match:
        speaker.radio_mode = mode_match.group(1)
    ht_match = re.search(r"HT Channel is (\d+)", text)
    if ht_match and ht_match.group(1) != "0":
        speaker.ht_channel_mhz = ht_match.group(1)
    chains_match = re.search(r"RF Chains: RX:(\d+)", text)
    if chains_match:
        speaker.rx_chains = int(chains_match.group(1))
    channel_match = re.search(r"Operating on channel (\d+)", text)
    if channel_match:
        speaker.wifi_channel_mhz = channel_match.group(1)
    home_match = re.search(r"Home channel is (\d+)", text)
    if home_match:
        speaker.wifi_home_channel_mhz = home_match.group(1)

    phy_match = re.search(r"PHY errors since last reading/reset:\s*(\d+)", text)
    if phy_match:
        speaker.phy_errors = int(phy_match.group(1))

    hal_match = re.search(r"HAL Reset Failures: cnt:\s*(\d+)", text)
    if hal_match:
        speaker.hal_reset_failures = int(hal_match.group(1))

    # Node xx:xx:xx:xx:xx:xx - FROM 63 {61} : TO 63 {61} : STP 03
    for match in re.finditer(
        r"^\s*Node ([0-9A-Fa-f:]{17}) - FROM (\d+)(?: \d+)? : TO (\d+)(?: \d+)? : STP (\w+)",
        text,
        re.MULTILINE,
    ):
        speaker.radio_peers.append(
            (match.group(1).upper(), int(match.group(2)), int(match.group(3)), match.group(4))
        )

    for match in re.finditer(r"Noise Floor:\s*(-?\d+)\s*dBm", text):
        speaker.noise_floor_dbm.append(int(match.group(1)))


def _apply_channel_map_roles(
    speaker: SpeakerDiagnostics,
    channel_map: str,
    coordinator: str,
    uuid: str,
) -> None:
    speaker.is_stereo_coordinator = uuid == coordinator and bool(channel_map)
    if not channel_map:
        return

    for part in channel_map.split(";"):
        if ":" not in part:
            continue
        uid, rest = part.split(":", 1)
        role = rest.split(",")[-1] if "," in rest else rest
        if uid != uuid:
            continue
        role_upper = role.upper()
        speaker.is_stereo_left = role_upper in {"LF", "L", "LEFT"}
        speaker.is_stereo_right = role_upper in {"RF", "R", "RIGHT"}


def _connection_type_label(code: str) -> str:
    return {
        "3": "Ethernet",
        "4": "Ethernet (WiFi disabled)",
        "5": "WiFi",
        "8": "Home theater link",
    }.get(code, code or "Unknown")


def _child_text(parent: ET.Element, tag: str) -> str:
    el = parent.find(tag)
    return (el.text or "").strip() if el is not None else ""


def _ip_from_location(location: str) -> str | None:
    match = re.match(r"https?://([^:/]+)", location)
    return match.group(1) if match else None
