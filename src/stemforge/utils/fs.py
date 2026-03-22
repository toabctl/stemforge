"""Filesystem helpers: session directory creation and path management."""

import re
import shutil
import unicodedata
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SessionPaths:
    """All relevant paths for a single pipeline run."""

    session_dir: Path
    captured_wav: Path
    stems_dir: Path
    midi_dir: Path

    def stem_wav(self, name: str) -> Path:
        return self.stems_dir / f"{name}.wav"

    def stem_midi(self, name: str) -> Path:
        return self.midi_dir / f"{name}.mid"


def _slugify(text: str, max_len: int = 40) -> str:
    """Convert arbitrary text to a safe directory-name component."""
    # Normalize unicode → ASCII approximation
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    # Replace whitespace and non-word chars with hyphens
    slug = re.sub(r"[^\w]+", "-", ascii_text).strip("-").lower()
    return slug[:max_len]


def build_session_paths(
    base_dir: Path,
    artist: str,
    title: str,
) -> SessionPaths:
    """Create an output directory tree, removing any previous run."""
    folder_name = f"{_slugify(artist)}-{_slugify(title)}"

    session_dir = base_dir / folder_name
    if session_dir.exists():
        shutil.rmtree(session_dir)

    stems_dir = session_dir / "stems"
    midi_dir = session_dir / "midi"

    for d in (session_dir, stems_dir, midi_dir):
        d.mkdir(parents=True, exist_ok=True)

    return SessionPaths(
        session_dir=session_dir,
        captured_wav=session_dir / "captured.wav",
        stems_dir=stems_dir,
        midi_dir=midi_dir,
    )
