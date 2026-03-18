"""Tests for Settings / configuration."""

import pytest
from pydantic import ValidationError

from stemforge.config import Settings


def test_settings_loads_with_env(monkeypatch) -> None:
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "cid")
    monkeypatch.setenv("SPOTIFY_CLIENT_SECRET", "csec")
    s = Settings()
    assert s.spotify_client_id == "cid"
    assert s.spotify_client_secret == "csec"
    assert s.capture_duration_seconds == 30
    assert s.demucs_model == "htdemucs"


def test_settings_missing_required(monkeypatch) -> None:
    monkeypatch.delenv("SPOTIFY_CLIENT_ID", raising=False)
    monkeypatch.delenv("SPOTIFY_CLIENT_SECRET", raising=False)
    with pytest.raises((ValidationError, Exception)):
        Settings(_env_file=None)


def test_capture_duration_bounds(monkeypatch) -> None:
    monkeypatch.setenv("CAPTURE_DURATION_SECONDS", "4")
    with pytest.raises(ValidationError):
        Settings()
