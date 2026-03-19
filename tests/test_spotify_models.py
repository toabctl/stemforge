"""Tests for Spotify domain models."""

import pytest

from stemforge.spotify.models import Device, Track


class TestTrack:
    def test_str_format(self) -> None:
        track = Track(
            uri="spotify:track:abc",
            name="Get Lucky",
            artist="Daft Punk",
            duration_ms=248186,
        )
        assert str(track) == "Daft Punk — Get Lucky (4:08)"

    def test_duration_seconds(self) -> None:
        track = Track(uri="u", name="n", artist="a", duration_ms=90000)
        assert track.duration_seconds == 90.0

    def test_str_zero_seconds(self) -> None:
        track = Track(uri="u", name="Song", artist="Artist", duration_ms=60000)
        assert str(track) == "Artist — Song (1:00)"

    def test_frozen(self) -> None:
        track = Track(uri="u", name="n", artist="a", duration_ms=1000)
        with pytest.raises(Exception):  # FrozenInstanceError
            track.name = "other"  # type: ignore[misc]


class TestDevice:
    def test_fields(self) -> None:
        device = Device(
            id="d1",
            name="My Speaker",
            type="Speaker",
            is_active=True,
            volume_percent=80,
        )
        assert device.id == "d1"
        assert device.is_active is True
        assert device.volume_percent == 80

    def test_volume_optional(self) -> None:
        device = Device(id="d1", name="n", type="t", is_active=False, volume_percent=None)
        assert device.volume_percent is None

    def test_frozen(self) -> None:
        device = Device(id="d1", name="n", type="t", is_active=False, volume_percent=None)
        with pytest.raises(Exception):
            device.name = "other"  # type: ignore[misc]
