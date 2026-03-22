"""Tests for PipeWire Spotify stream node discovery."""

from unittest.mock import patch

from stemforge.capture.monitor import get_spotify_monitor_source

_PW_DUMP_SPOTIFY = [
    {
        "id": 42,
        "type": "PipeWire:Interface:Node",
        "info": {
            "props": {
                "media.class": "Stream/Output/Audio",
                "node.name": "spotify-output",
                "application.name": "Spotify",
                "application.process.binary": "spotify",
            }
        },
    },
]

_PW_DUMP_NO_SPOTIFY = [
    {
        "id": 10,
        "type": "PipeWire:Interface:Node",
        "info": {
            "props": {
                "media.class": "Stream/Output/Audio",
                "node.name": "firefox-output",
                "application.name": "Firefox",
                "application.process.binary": "firefox",
            }
        },
    },
]


def test_get_spotify_monitor_source_found() -> None:
    with patch("stemforge.capture.monitor._pw_dump", return_value=_PW_DUMP_SPOTIFY):
        result = get_spotify_monitor_source()
    assert result == "spotify-output"


def test_get_spotify_monitor_source_not_found() -> None:
    with patch("stemforge.capture.monitor._pw_dump", return_value=_PW_DUMP_NO_SPOTIFY):
        result = get_spotify_monitor_source()
    assert result is None


def test_get_spotify_monitor_source_on_error() -> None:
    with patch("stemforge.capture.monitor._pw_dump", side_effect=Exception("no pw-dump")):
        result = get_spotify_monitor_source()
    assert result is None
