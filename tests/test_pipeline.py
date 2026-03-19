"""Tests for pipeline helpers."""

import numpy as np
import pytest
import soundfile as sf

from stemforge.exceptions import CaptureError
from stemforge.pipeline import _assert_audio_not_silent


def _write_wav(path, data: np.ndarray, samplerate: int = 44100) -> None:
    sf.write(str(path), data, samplerate)


def test_assert_audio_not_silent_passes_for_loud_audio(tmp_path) -> None:
    data = np.sin(np.linspace(0, 2 * np.pi * 440, 44100)).astype(np.float32)
    wav = tmp_path / "loud.wav"
    _write_wav(wav, data)
    _assert_audio_not_silent(wav)  # must not raise


def test_assert_audio_not_silent_raises_for_zeros(tmp_path) -> None:
    data = np.zeros(44100, dtype=np.float32)
    wav = tmp_path / "silent.wav"
    _write_wav(wav, data)
    with pytest.raises(CaptureError, match="silent"):
        _assert_audio_not_silent(wav)


def test_assert_audio_not_silent_raises_for_near_silence(tmp_path) -> None:
    # RMS well below 1e-4
    data = np.full(44100, 1e-6, dtype=np.float32)
    wav = tmp_path / "near_silent.wav"
    _write_wav(wav, data)
    with pytest.raises(CaptureError, match="silent"):
        _assert_audio_not_silent(wav)


def test_assert_audio_not_silent_stereo(tmp_path) -> None:
    samples = np.sin(np.linspace(0, 2 * np.pi * 440, 44100)).astype(np.float32)
    stereo = np.column_stack([samples, samples])
    wav = tmp_path / "stereo.wav"
    _write_wav(wav, stereo)
    _assert_audio_not_silent(wav)  # must not raise
