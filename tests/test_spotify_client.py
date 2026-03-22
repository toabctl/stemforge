"""Tests for SpotifyClient."""

from unittest.mock import MagicMock, patch

import pytest

from stemforge.exceptions import NoActiveDeviceError, PlaybackError
from stemforge.spotify.models import Device


def _make_device(name: str, is_active: bool = False) -> Device:
    return Device(id=name, name=name, type="Computer", is_active=is_active, volume_percent=100)


def _make_client(devices_sequence: list[list[Device]]) -> "SpotifyClient":  # noqa: F821
    """Build a SpotifyClient whose list_devices() returns successive lists."""
    from stemforge.config import Settings
    from stemforge.spotify.client import SpotifyClient

    settings = Settings()

    with patch("stemforge.spotify.client._make_auth_manager"):
        client = SpotifyClient.__new__(SpotifyClient)
        client._settings = settings

    call_iter = iter(devices_sequence)

    def _list_devices():
        return next(call_iter, [])

    client.list_devices = _list_devices
    return client


def _make_playback_client() -> tuple["SpotifyClient", MagicMock]:  # noqa: F821
    """Build a SpotifyClient with a mocked spotipy instance."""
    from stemforge.config import Settings
    from stemforge.spotify.client import SpotifyClient

    settings = Settings()
    mock_sp = MagicMock()

    with patch("stemforge.spotify.client._make_auth_manager"):
        client = SpotifyClient.__new__(SpotifyClient)
        client._settings = settings
        client._sp = mock_sp

    return client, mock_sp


# ── Preferred-name matching ───────────────────────────────────────────────────


def test_get_active_device_preferred_name_match() -> None:
    client = _make_client([[_make_device("ThinkPad t14"), _make_device("frame13")]])
    device = client.get_active_device(preferred_name="t14")
    assert device.name == "ThinkPad t14"


def test_get_active_device_preferred_name_case_insensitive() -> None:
    client = _make_client([[_make_device("ThinkPad T14")]])
    device = client.get_active_device(preferred_name="thinkpad")
    assert "ThinkPad" in device.name


def test_get_active_device_preferred_name_not_found_raises() -> None:
    client = _make_client([[], [], [], [], []])  # 5 empty attempts
    with (
        patch("stemforge.spotify.client.time.sleep"),
        pytest.raises(NoActiveDeviceError, match="t14"),
    ):
        client.get_active_device(preferred_name="t14", retries=5, delay=0)


# ── Active device fallback ────────────────────────────────────────────────────


def test_get_active_device_returns_active() -> None:
    devices = [_make_device("idle"), _make_device("active", is_active=True)]
    client = _make_client([devices])
    device = client.get_active_device()
    assert device.name == "active"


def test_get_active_device_falls_back_to_first_when_none_active() -> None:
    devices = [_make_device("only-one")]
    client = _make_client([devices])
    device = client.get_active_device()
    assert device.name == "only-one"


def test_get_active_device_no_devices_raises() -> None:
    client = _make_client([[], [], []])
    with (
        patch("stemforge.spotify.client.time.sleep"),
        pytest.raises(NoActiveDeviceError, match="No active"),
    ):
        client.get_active_device(retries=3, delay=0)


# ── Retry behaviour ───────────────────────────────────────────────────────────


def test_get_active_device_retries_until_found() -> None:
    """Device appears on the third attempt."""
    client = _make_client([[], [], [_make_device("late-device", is_active=True)]])
    with patch("stemforge.spotify.client.time.sleep"):
        device = client.get_active_device(retries=5, delay=0)
    assert device.name == "late-device"


# ── seek_to_position ─────────────────────────────────────────────────────────


def test_seek_to_position_converts_seconds_to_ms() -> None:
    client, mock_sp = _make_playback_client()
    client.seek_to_position("dev-1", position_seconds=30)
    mock_sp.seek_track.assert_called_once_with(30_000, device_id="dev-1")


def test_seek_to_position_defaults_to_zero() -> None:
    client, mock_sp = _make_playback_client()
    client.seek_to_position("dev-1")
    mock_sp.seek_track.assert_called_once_with(0, device_id="dev-1")


def test_seek_to_position_raises_on_error() -> None:
    client, mock_sp = _make_playback_client()
    mock_sp.seek_track.side_effect = Exception("API error")
    with pytest.raises(PlaybackError, match="Failed to seek"):
        client.seek_to_position("dev-1", position_seconds=10)
