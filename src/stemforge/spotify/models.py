"""Domain models for Spotify API objects."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Track:
    uri: str
    name: str
    artist: str
    duration_ms: int

    @property
    def duration_seconds(self) -> float:
        return self.duration_ms / 1000

    def __str__(self) -> str:
        mins, secs = divmod(self.duration_ms // 1000, 60)
        return f"{self.artist} — {self.name} ({mins}:{secs:02d})"


@dataclass(frozen=True)
class Device:
    id: str
    name: str
    type: str
    is_active: bool
    volume_percent: int | None
