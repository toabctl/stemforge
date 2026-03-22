"""Pipeline orchestrator.

Sequences the four stages in order, threading outputs between stages:

  1. Spotify search + playback trigger
  2. PipeWire audio capture (pw-record)
  3. Stem separation (Demucs)
  4. MIDI conversion (Basic-Pitch)

All stage-specific exceptions are allowed to propagate so the CLI can
surface actionable error messages and set appropriate exit codes.
"""

import logging
import time

import numpy as np
import soundfile as sf
from dataclasses import dataclass, field
from pathlib import Path

from stemforge.capture.monitor import get_spotify_monitor_source
from stemforge.exceptions import CaptureError
from stemforge.capture.recorder import AudioRecorder
from stemforge.config import Settings
from stemforge.midi.converter import MidiConverter
from stemforge.separation.separator import StemSeparator
from stemforge.spotify.client import SpotifyClient
from stemforge.spotify.models import Device, Track
from stemforge.utils.fs import SessionPaths, build_session_paths

log = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    """All artefacts produced by a single pipeline run."""

    track: Track
    device: Device
    session: SessionPaths
    captured_wav: Path
    stem_paths: dict[str, Path] = field(default_factory=dict)
    midi_paths: dict[str, Path] = field(default_factory=dict)


class RecordPipeline:
    """Orchestrates Spotify → WAV capture only (no separation or MIDI)."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._spotify = SpotifyClient(settings)
        self._recorder = AudioRecorder()

    def run(
        self,
        query: str,
        duration: int | None = None,
        start: int = 0,
    ) -> PipelineResult:
        """Search for a track, record it, and return the captured WAV path."""
        capture_duration = duration or self._settings.capture_duration_seconds

        track = self._spotify.search(query)
        device = self._spotify.get_active_device(
            preferred_name=self._settings.spotify_device_name
        )
        session = build_session_paths(
            self._settings.output_dir,
            artist=track.artist,
            title=track.name,
        )
        log.info("Session directory: %s", session.session_dir)

        captured_wav = _capture_spotify(
            spotify=self._spotify,
            recorder=self._recorder,
            settings=self._settings,
            track=track,
            device=device,
            session=session,
            duration=capture_duration,
            start=start,
        )

        return PipelineResult(
            track=track,
            device=device,
            session=session,
            captured_wav=captured_wav,
        )


class Pipeline:
    """Orchestrates the full Spotify → WAV → stems → MIDI pipeline."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        # Initialise heavy components eagerly so model-load errors surface early
        log.info("Initialising pipeline components…")
        self._spotify = SpotifyClient(settings)
        self._recorder = AudioRecorder()
        self._separator = StemSeparator(settings)
        self._converter = MidiConverter(settings)
        log.info("All components ready.")

    def run(
        self,
        query: str,
        duration: int | None = None,
        start: int = 0,
    ) -> PipelineResult:
        """Execute the full pipeline for *query*.

        Args:
            query: Free-text Spotify search string (artist, title, or both).
            duration: Override capture duration in seconds (default from settings).
            start: Start position in seconds (default 0).

        Returns:
            PipelineResult with paths to all produced artefacts.
        """
        capture_duration = duration or self._settings.capture_duration_seconds

        track = self._spotify.search(query)
        device = self._spotify.get_active_device(
            preferred_name=self._settings.spotify_device_name
        )
        session = build_session_paths(
            self._settings.output_dir,
            artist=track.artist,
            title=track.name,
        )
        log.info("Session directory: %s", session.session_dir)

        captured_wav = _capture_spotify(
            spotify=self._spotify,
            recorder=self._recorder,
            settings=self._settings,
            track=track,
            device=device,
            session=session,
            duration=capture_duration,
            start=start,
        )

        stem_paths = self._separator.separate(captured_wav, session.stems_dir)
        midi_paths = self._converter.convert_all(stem_paths, session.midi_dir)

        return PipelineResult(
            track=track,
            device=device,
            session=session,
            captured_wav=captured_wav,
            stem_paths=stem_paths,
            midi_paths=midi_paths,
        )


def _capture_spotify(
    *,
    spotify: SpotifyClient,
    recorder: AudioRecorder,
    settings: Settings,
    track: Track,
    device: Device,
    session: SessionPaths,
    duration: int,
    start: int,
) -> Path:
    """Start Spotify playback, discover the PipeWire node, and record to WAV."""
    spotify.start_playback(track.uri, device.id)

    playback_start = time.monotonic()
    source = settings.pipewire_sink or None
    if source is None:
        _POLL_INTERVAL = 0.5
        deadline = playback_start + settings.playback_start_delay_seconds
        while time.monotonic() < deadline:
            time.sleep(_POLL_INTERVAL)
            source = get_spotify_monitor_source()
            if source:
                break
        if source is None:
            raise CaptureError(
                "Could not find Spotify's stream node in the PipeWire graph.\n"
                "Make sure Spotify is playing on this machine.\n"
                "You can also set PIPEWIRE_SINK in your .env to the node name shown by:\n"
                '  pw-dump | jq -r \'.[] | select(.info.props["media.class"] == '
                '"Stream/Output/Audio") | .info.props["node.name"]\''
            )

    log.info("Capturing from node: %s", source)
    spotify.seek_to_position(device.id, position_seconds=start)

    captured_wav = recorder.record(
        output_path=session.captured_wav,
        source=source,
        duration=duration,
        sample_rate=settings.capture_sample_rate,
        channels=settings.capture_channels,
    )

    spotify.pause_playback(device.id)
    _assert_audio_not_silent(captured_wav)
    return captured_wav


_SILENCE_RMS_THRESHOLD = 1e-4  # anything below this is considered silence


def _assert_audio_not_silent(wav_path: Path) -> None:
    """Raise CaptureError if the recorded WAV is silent or near-silent.

    This catches the common failure mode where Spotify is playing on a
    different device and the monitor records nothing but zeros.
    """
    data, _ = sf.read(str(wav_path), dtype="float32")
    rms = float(np.sqrt(np.mean(data**2)))
    log.debug("Captured audio RMS: %.6f", rms)
    if rms < _SILENCE_RMS_THRESHOLD:
        raise CaptureError(
            f"Captured audio is silent (RMS={rms:.2e}). "
            "Check that:\n"
            "  • Spotify volume is not zero\n"
            "  • Spotify is playing on this machine, not a remote device\n"
            "Run 'stemforge devices' to see available devices and set "
            "SPOTIFY_DEVICE_NAME in your .env to pin the correct one."
        )
