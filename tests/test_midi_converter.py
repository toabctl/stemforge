"""Tests for MidiConverter helpers."""

from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest
import soundfile as sf

from stemforge.exceptions import ConversionError
from stemforge.midi.converter import _normalize_wav

# ── _normalize_wav ────────────────────────────────────────────────────────────


def test_normalize_wav_scales_to_near_one(tmp_path: Path) -> None:
    src = tmp_path / "src.wav"
    dst = tmp_path / "dst.wav"
    data = np.array([[0.1, -0.2], [0.05, 0.15]], dtype=np.float32)
    sf.write(str(src), data, 44100)

    _normalize_wav(src, dst)

    result, _ = sf.read(str(dst), always_2d=True)
    assert pytest.approx(np.abs(result).max(), abs=1e-4) == 0.99


def test_normalize_wav_silent_input_unchanged(tmp_path: Path) -> None:
    """A silent file should not blow up — peak=0 branch is a no-op."""
    src = tmp_path / "silent.wav"
    dst = tmp_path / "out.wav"
    data = np.zeros((1024, 2), dtype=np.float32)
    sf.write(str(src), data, 44100)

    _normalize_wav(src, dst)  # must not raise

    result, _ = sf.read(str(dst), always_2d=True)
    assert np.all(result == 0.0)


def test_normalize_wav_already_loud(tmp_path: Path) -> None:
    src = tmp_path / "loud.wav"
    dst = tmp_path / "out.wav"
    data = np.ones((512,), dtype=np.float32)
    sf.write(str(src), data, 44100)

    _normalize_wav(src, dst)

    result, _ = sf.read(str(dst))
    assert pytest.approx(result.max(), abs=1e-4) == 0.99


# ── convert_all skip behaviour ────────────────────────────────────────────────


def test_convert_all_skips_failed_stems(tmp_path: Path, settings) -> None:
    """convert_all must log and continue when one stem fails."""
    from stemforge.midi.converter import MidiConverter

    converter = MidiConverter.__new__(MidiConverter)
    converter._settings = settings
    converter._model = MagicMock()

    stems = {
        "vocals": tmp_path / "vocals.wav",
        "bass": tmp_path / "bass.wav",
    }
    for p in stems.values():
        p.touch()

    def fake_convert(wav, out_dir, name):
        if name == "vocals":
            raise ConversionError("vocals failed")
        midi = out_dir / f"{name}.mid"
        midi.write_bytes(b"\x00" * 100)
        return midi

    converter.convert = fake_convert

    result = converter.convert_all(stems, tmp_path)

    assert "vocals" not in result
    assert "bass" in result
