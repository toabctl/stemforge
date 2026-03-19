"""Tests for PulseAudio monitor source discovery."""

from unittest.mock import patch

from stemforge.capture.monitor import get_default_monitor_source, list_monitor_sources

_PACTL_SHORT_OUTPUT = """\
57\talsa_output.pci-0000_07_00.6.analog-stereo.monitor\tPipeWire\ts32le 2ch 48000Hz\tIDLE
58\talsa_input.pci-0000_07_00.6.analog-stereo\tPipeWire\ts32le 2ch 48000Hz\tIDLE
"""


def test_list_monitor_sources() -> None:
    with patch(
        "stemforge.capture.monitor.subprocess.check_output",
        return_value=_PACTL_SHORT_OUTPUT,
    ):
        sources = list_monitor_sources()
    assert sources == ["alsa_output.pci-0000_07_00.6.analog-stereo.monitor"]


def test_get_default_monitor_source_resolves() -> None:
    sink = "alsa_output.pci-0000_07_00.6.analog-stereo"
    monitor = f"{sink}.monitor"

    with (
        patch(
            "stemforge.capture.monitor._get_default_sink",
            return_value=sink,
        ),
        patch(
            "stemforge.capture.monitor._source_exists",
            return_value=True,
        ),
    ):
        result = get_default_monitor_source()

    assert result == monitor


def test_get_default_monitor_source_fallback_on_error() -> None:
    with patch("stemforge.capture.monitor._get_default_sink", side_effect=Exception("no pactl")):
        result = get_default_monitor_source()
    assert result == "@DEFAULT_MONITOR@"
