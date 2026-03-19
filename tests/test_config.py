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
    # Current defaults
    assert s.capture_duration_seconds == 60
    assert s.demucs_model == "htdemucs_ft"
    assert s.demucs_shifts == 2


def test_settings_missing_required(monkeypatch) -> None:
    monkeypatch.delenv("SPOTIFY_CLIENT_ID", raising=False)
    monkeypatch.delenv("SPOTIFY_CLIENT_SECRET", raising=False)
    with pytest.raises((ValidationError, Exception)):
        Settings(_env_file=None)


def test_capture_duration_too_low(monkeypatch) -> None:
    monkeypatch.setenv("CAPTURE_DURATION_SECONDS", "4")
    with pytest.raises(ValidationError):
        Settings()


def test_capture_duration_too_high(monkeypatch) -> None:
    monkeypatch.setenv("CAPTURE_DURATION_SECONDS", "301")
    with pytest.raises(ValidationError):
        Settings()


def test_demucs_shifts_bounds(monkeypatch) -> None:
    monkeypatch.setenv("DEMUCS_SHIFTS", "0")
    with pytest.raises(ValidationError):
        Settings()


def test_demucs_device_invalid(monkeypatch) -> None:
    monkeypatch.setenv("DEMUCS_DEVICE", "tpu")
    with pytest.raises(ValidationError):
        Settings()


def test_output_dir_is_absolute(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("OUTPUT_DIR", "relative/path")
    s = Settings()
    assert s.output_dir.is_absolute()


def test_redirect_uri_default() -> None:
    s = Settings()
    assert s.spotify_redirect_uri == "http://127.0.0.1:8888/callback"
