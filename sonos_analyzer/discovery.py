"""Discover Sonos speakers on the local network via SSDP."""

from __future__ import annotations

import re
import select
import socket
import struct
import time
from dataclasses import dataclass


SSDP_MCAST = ("239.255.255.250", 1900)
SEARCH_TARGET = "urn:schemas-upnp-org:device:ZonePlayer:1"
SEARCH_MESSAGE = (
    "M-SEARCH * HTTP/1.1\r\n"
    f"HOST: {SSDP_MCAST[0]}:{SSDP_MCAST[1]}\r\n"
    'MAN: "ssdp:discover"\r\n'
    "MX: 2\r\n"
    f"ST: {SEARCH_TARGET}\r\n"
    "\r\n"
).encode("ascii")

LOCATION_RE = re.compile(r"^LOCATION:\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE)


@dataclass(frozen=True)
class DiscoveredSpeaker:
    ip: str
    location_url: str


def interface_address(interface: str) -> str:
    """Resolve an interface name (e.g. eth0) or IPv4 address to its IPv4 address."""
    try:
        socket.inet_aton(interface)
        return interface
    except OSError:
        pass

    import fcntl  # Linux only; names cannot be resolved elsewhere

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        ifreq = struct.pack("256s", interface.encode()[:15])
        # SIOCGIFADDR
        return socket.inet_ntoa(fcntl.ioctl(sock.fileno(), 0x8915, ifreq)[20:24])


def local_addresses() -> list[str]:
    """IPv4 addresses of this host's non-loopback interfaces (empty if they cannot be listed)."""
    addresses: list[str] = []
    try:
        names = [name for _index, name in socket.if_nameindex()]
    except (AttributeError, OSError):
        return addresses
    for name in names:
        # Docker's own bridges only lead to containers.
        if name.startswith(("docker", "br-", "veth")):
            continue
        try:
            address = interface_address(name)
        except (ImportError, OSError):
            continue  # no IPv4 address, or names cannot be resolved on this platform
        if not address.startswith("127.") and address not in addresses:
            addresses.append(address)
    return addresses


def off_network_hint(ips: list[str]) -> str:
    """Explain unreachable speakers that sit on a network this host has no address on."""
    local = local_addresses()
    prefixes = {ip.rsplit(".", 1)[0] for ip in local}
    foreign = sorted({ip.rsplit(".", 1)[0] for ip in ips} - prefixes)
    if not local or not foreign:
        return ""
    return (
        f"The speakers are on {', '.join(f'{p}.x' for p in foreign)}, but this host has no address on that "
        f"network (it has {', '.join(local)}). Check that its connection to the speakers' network is up."
    )


def discover_speakers(timeout: float = 3.0, interface: str | None = None) -> list[DiscoveredSpeaker]:
    """Send SSDP M-SEARCH and collect Sonos ZonePlayer endpoints.

    interface: name or IPv4 address of the one network interface to search on.
    By default every interface is searched, so multi-homed hosts find speakers
    whichever network they are on.
    """
    if interface:
        local_ips = [interface_address(interface)]
    else:
        # Fall back to the OS's default multicast route when interfaces cannot be listed.
        local_ips = local_addresses() or [""]

    socks: list[socket.socket] = []
    seen: set[str] = set()
    speakers: list[DiscoveredSpeaker] = []
    try:
        for local_ip in local_ips:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            try:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.bind((local_ip, 0))
                if local_ip:
                    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton(local_ip))
                sock.sendto(SEARCH_MESSAGE, SSDP_MCAST)
            except OSError:
                # An interface that is down or has no route; a named one is an error.
                sock.close()
                if interface:
                    raise
                continue
            socks.append(sock)

        end = time.monotonic() + timeout
        while socks and (remaining := end - time.monotonic()) > 0:
            readable, _, _ = select.select(socks, [], [], min(0.5, remaining))
            for sock in readable:
                try:
                    data, _addr = sock.recvfrom(65535)
                except OSError:
                    continue

                text = data.decode("utf-8", errors="replace")
                # Other UPnP devices sometimes answer searches that are not for them.
                if "sonos" not in text.lower() and SEARCH_TARGET not in text:
                    continue
                match = LOCATION_RE.search(text)
                if not match:
                    continue

                location = match.group(1).strip()
                ip = _ip_from_location(location)
                if not ip or ip in seen:
                    continue
                seen.add(ip)
                speakers.append(DiscoveredSpeaker(ip=ip, location_url=location))
    finally:
        for sock in socks:
            sock.close()

    return sorted(speakers, key=lambda s: s.ip)


def _ip_from_location(location: str) -> str | None:
    # http://192.168.1.165:1400/xml/device_description.xml
    match = re.match(r"https?://([^:/]+)", location)
    return match.group(1) if match else None
