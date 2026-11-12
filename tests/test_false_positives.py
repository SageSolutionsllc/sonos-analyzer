"""Regression tests for findings that misfired in normal homes.

Run from the repository root: python -m unittest discover -s tests
All data here is synthetic; no speakers are contacted.
"""

from __future__ import annotations

import unittest

from sonos_analyzer.analyze import _bad_link, analyze
from sonos_analyzer.parse import (
    HouseholdSnapshot,
    SpeakerDiagnostics,
    _parse_ifconfig,
    merge_speakers,
)
from sonos_analyzer.report import report_payload


def wifi(name, ip, freq="5180", room=None, **kw):
    return SpeakerDiagnostics(
        zone_name=name, ip_address=ip, room_name=name, room_uid=room or ip,
        connection_type_code="5", wifi_channel_mhz=freq, software_version="85.0", **kw
    )


def wired(name, ip, room=None, **kw):
    return SpeakerDiagnostics(
        zone_name=name, ip_address=ip, room_name=name, room_uid=room or ip,
        connection_type_code="3", ethernet_link=True, software_version="85.0", **kw
    )


def satellite(name, ip, room, role, freq="5745"):
    return SpeakerDiagnostics(
        zone_name=name, ip_address=ip, room_name=name, room_uid=room, role=role,
        bond="home_theater", connection_type_code="8", wifi_channel_mhz=freq, software_version="85.0",
    )


def run(*speakers, errors=()):
    snap = HouseholdSnapshot(speakers={sp.ip_address: sp for sp in speakers}, fetch_errors=list(errors))
    return analyze(snap)


def titles(report):
    return [f.title for f in report.findings]


class ParserTests(unittest.TestCase):
    def test_later_interface_does_not_overwrite_eth0(self):
        text = "\n".join([
            "ath0      Link encap:Ethernet",
            "          RX packets:9 errors:9 dropped:9 overruns:0 frame:0",
            "br0       Link encap:Ethernet",
            "          RX packets:1000 errors:0 dropped:50 overruns:0 frame:0",
            "          TX packets:900 errors:0 dropped:0 overruns:0 carrier:0",
            "eth0      Link encap:Ethernet",
            "          RX packets:500000 errors:0 dropped:0 overruns:0 frame:0",
            "          TX packets:400000 errors:0 dropped:0 overruns:0 carrier:0",
            "lo        Link encap:Local Loopback",
            "          RX packets:7 errors:7 dropped:7 overruns:0 frame:0",
            "          TX packets:7 errors:7 dropped:7 overruns:0 carrier:0",
        ])
        sp = SpeakerDiagnostics(zone_name="x", ip_address="10.0.0.1")
        _parse_ifconfig(text, sp)
        self.assertEqual((sp.eth0.rx_packets, sp.eth0.rx_errors), (500000, 0))
        self.assertEqual((sp.br0.rx_packets, sp.br0.rx_dropped), (1000, 50))

    def test_wifi_disabled_survives_merge(self):
        a = {"10.0.0.1": SpeakerDiagnostics(zone_name="x", ip_address="10.0.0.1")}
        b = {"10.0.0.1": SpeakerDiagnostics(zone_name="x", ip_address="10.0.0.1", wifi_enabled=False)}
        self.assertIs(merge_speakers(a, b)["10.0.0.1"].wifi_enabled, False)

    def test_link_speed(self):
        self.assertFalse(_bad_link("100FD"))
        self.assertFalse(_bad_link("1000"))
        self.assertTrue(_bad_link("10FD"))
        self.assertTrue(_bad_link("100HD"))


class FalsePositiveTests(unittest.TestCase):
    def test_wired_soundbar_with_satellites_keeps_its_radio(self):
        bar = wired("Living Room", "10.0.0.10", room="LR", bond="home_theater", phy_errors=0)
        report = run(
            bar,
            satellite("Living Room", "10.0.0.11", "LR", "Sub"),
            satellite("Living Room", "10.0.0.12", "LR", "Left surround"),
        )
        self.assertFalse(any("radio still on" in t for t in titles(report)))

    def test_lone_wired_speaker_with_idle_radio_is_still_reported(self):
        report = run(wired("Office", "10.0.0.20", phy_errors=0), wifi("Kitchen", "10.0.0.21"))
        self.assertTrue(any("radio still on" in t for t in titles(report)))

    def test_pair_with_wired_sub_is_not_mixed(self):
        report = run(
            wifi("Den", "10.0.0.30", room="DEN", role="Left", bond="stereo_pair"),
            wifi("Den", "10.0.0.31", room="DEN", role="Right", bond="stereo_pair"),
            wired("Den", "10.0.0.32", room="DEN", role="Sub", bond="stereo_pair"),
        )
        self.assertFalse(any("mixed wired" in t for t in titles(report)))
        self.assertTrue(any("is consistent" in t for t in titles(report)))

    def test_phy_errors_compared_within_band(self):
        # Busy 2.4 GHz speakers must not be flagged against a quiet 5 GHz household.
        speakers = [wifi(f"R{i}", f"10.0.1.{i}", phy_error_rate=50.0, phy_error_rates=[50.0] * 3) for i in range(3)]
        speakers += [
            wifi(f"S{i}", f"10.0.2.{i}", freq="2437", phy_error_rate=1500.0, phy_error_rates=[1500.0] * 3)
            for i in range(3)
        ]
        self.assertFalse(any("noisy" in t for t in titles(run(*speakers))))

    def test_phy_spike_in_one_window_is_ignored(self):
        speakers = [wifi(f"R{i}", f"10.0.1.{i}", phy_error_rate=50.0, phy_error_rates=[50.0] * 3) for i in range(4)]
        speakers.append(wifi("Spike", "10.0.1.9", phy_error_rate=60.0, phy_error_rates=[60.0, 9000.0, 55.0]))
        self.assertFalse(any("noisy" in t for t in titles(run(*speakers))))

    def test_persistent_phy_outlier_is_flagged_with_low_confidence(self):
        speakers = [wifi(f"R{i}", f"10.0.1.{i}", phy_error_rate=50.0, phy_error_rates=[50.0] * 3) for i in range(4)]
        speakers.append(wifi("Garage", "10.0.1.9", phy_error_rate=4000.0, phy_error_rates=[3800.0, 4000.0, 4200.0]))
        noisy = [f for f in run(*speakers).findings if "noisy" in f.title]
        self.assertEqual(len(noisy), 1)
        self.assertEqual(noisy[0].confidence, "low")

    def test_noise_floor_per_band(self):
        quiet_24 = wifi("Kitchen", "10.0.0.40", freq="2437", noise_floor_dbm=[-82, -83])
        self.assertFalse(any("noise floor" in t for t in titles(run(quiet_24))))
        loud_5 = wifi("Kitchen", "10.0.0.40", noise_floor_dbm=[-82, -83])
        self.assertTrue(any("noise floor" in t for t in titles(run(loud_5))))

    def test_lone_wired_stp_speaker_is_not_a_mesh(self):
        report = run(
            wired("Office", "10.0.0.50", stp_enabled=True, phy_errors=0),
            wifi("Kitchen", "10.0.0.51", model_name="Era 100"),
        )
        self.assertFalse(any("SonosNet" in t for t in titles(report)))

    def test_two_wired_stp_speakers_are_flagged(self):
        report = run(
            wired("Office", "10.0.0.60", stp_enabled=True),
            wired("Bar", "10.0.0.61", stp_enabled=True),
        )
        self.assertTrue(any("running spanning tree" in t for t in titles(report)))

    def test_missing_version_is_not_a_mismatch(self):
        a = wifi("Den", "10.0.0.70", room="DEN", role="Left", bond="stereo_pair")
        b = wifi("Den", "10.0.0.71", room="DEN", role="Right", bond="stereo_pair")
        b.software_version = ""
        report = run(a, b)
        self.assertFalse(any("different firmware" in t or "behind on firmware" in t for t in titles(report)))

    def test_unreachable_speakers_block_all_clear(self):
        report = run(wifi("Kitchen", "10.0.0.80"), errors=["10.0.0.81: no response on port 1400"])
        self.assertTrue(any("could not be read" in t for t in titles(report)))
        self.assertNotIn("No significant issues detected.", report.recommendations)

    def test_payload_carries_join_keys_and_confidence(self):
        payload = report_payload(run(wifi("Kitchen", "10.0.0.90", mac_address="00:0E:58:AA:BB:CC")))
        self.assertEqual(payload["speakers"][0]["mac_address"], "00:0E:58:AA:BB:CC")
        self.assertTrue(all("confidence" in f for f in payload["findings"]))


if __name__ == "__main__":
    unittest.main()
