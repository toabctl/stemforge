"""Central configuration via Pydantic Settings.

All values can be overridden via environment variables or a .env file.
The application fails fast on startup if required credentials are missing.
"""

from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Spotify OAuth ────────────────────────────────────────────────────────
    spotify_client_id: str = Field(..., description="Spotify app Client ID")
    spotify_client_secret: str = Field(..., description="Spotify app Client Secret")
    spotify_redirect_uri: str = Field(
        default="http://127.0.0.1:8888/callback",
        description="OAuth redirect URI (must match your Spotify app settings)",
    )

    spotify_device_name: str = Field(
        default="",
        description="Preferred Spotify device name (partial match, case-insensitive). Leave empty to use the active device.",
    )

    # ── Audio capture ────────────────────────────────────────────────────────
    pulse_monitor_source: str = Field(
        default="@DEFAULT_MONITOR@",
        description="PulseAudio/PipeWire monitor source name",
    )
    capture_duration_seconds: int = Field(
        default=60, ge=5, le=300, description="How many seconds of audio to capture"
    )
    capture_sample_rate: int = Field(default=44100, description="Sample rate in Hz")
    capture_channels: int = Field(default=2, description="1=mono, 2=stereo")

    # ── Stem separation (Demucs) ─────────────────────────────────────────────
    demucs_model: str = Field(
        default="htdemucs_ft",
        description="Demucs model name (htdemucs, htdemucs_ft, mdx_extra, …)",
    )
    demucs_device: Literal["cuda", "cpu", "mps"] = Field(
        default="cpu",
        description="Torch device for Demucs inference",
    )
    demucs_shifts: int = Field(
        default=2,
        ge=1,
        le=10,
        description="Number of random shifts for equivariant stabilisation (higher = slower but better)",
    )

    # ── Basic-Pitch MIDI conversion ──────────────────────────────────────────
    midi_onset_threshold: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Note onset sensitivity (lower = more notes detected)",
    )
    midi_frame_threshold: float = Field(
        default=0.1,
        ge=0.0,
        le=1.0,
        description="Note frame sensitivity (lower = more notes detected)",
    )
    midi_min_note_length: float = Field(
        default=127.7,
        description="Minimum note length in milliseconds",
    )

    # ── Pipeline timing ──────────────────────────────────────────────────────
    playback_start_delay_seconds: float = Field(
        default=3.0,
        ge=0.5,
        description="Seconds to wait after triggering playback before recording starts",
    )

    # ── Output ───────────────────────────────────────────────────────────────
    output_dir: Path = Field(default=Path("output"), description="Base output directory")

    @field_validator("output_dir", mode="before")
    @classmethod
    def _expand_output_dir(cls, v: object) -> Path:
        return Path(str(v)).expanduser().resolve()
