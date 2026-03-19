"""Typed exceptions for each pipeline stage.

Each stage raises its own exception type so the orchestrator can catch
selectively and the user gets a clear, actionable error message.
"""


class StemforgeError(Exception):
    """Base class for all stemforge errors."""


# ── Spotify stage ────────────────────────────────────────────────────────────


class SpotifyAuthError(StemforgeError):
    """OAuth flow failed or stored token is invalid."""


class NoActiveDeviceError(StemforgeError):
    """No active Spotify client found on any device."""


class TrackNotFoundError(StemforgeError):
    """Spotify search returned no results for the given query."""


class PlaybackError(StemforgeError):
    """Spotify failed to start or stop playback."""


# ── Capture stage ────────────────────────────────────────────────────────────


class CaptureError(StemforgeError):
    """parecord failed to start, crashed, or produced an empty file."""


class MonitorSourceError(StemforgeError):
    """Could not discover a PulseAudio/PipeWire monitor source."""


# ── Separation stage ─────────────────────────────────────────────────────────


class SeparationError(StemforgeError):
    """Demucs model load or inference failed."""


# ── MIDI conversion stage ────────────────────────────────────────────────────


class ConversionError(StemforgeError):
    """Basic-Pitch inference or MIDI write failed."""
