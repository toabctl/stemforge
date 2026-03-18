"""Tests for AudioRecorder."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from stemforge.capture.recorder import AudioRecorder
from stemforge.exceptions import CaptureError


def test_record_missing_parecord(tmp_path: Path) -> None:
    with patch("stemforge.capture.recorder.shutil.which", return_value=None):
        recorder = AudioRecorder()
        with pytest.raises(CaptureError, match="parecord not found"):
            recorder.record(tmp_path / "out.wav", "@DEFAULT_MONITOR@", duration=1)


def test_record_nonzero_exit(tmp_path: Path) -> None:
    out = tmp_path / "out.wav"

    mock_proc = MagicMock()
    mock_proc.returncode = 1
    mock_proc.communicate.return_value = (b"", b"Connection refused")

    with (
        patch("stemforge.capture.recorder.shutil.which", return_value="/usr/bin/parecord"),
        patch("stemforge.capture.recorder.subprocess.Popen", return_value=mock_proc),
        patch("stemforge.capture.recorder.time.sleep"),
    ):
        recorder = AudioRecorder()
        with pytest.raises(CaptureError, match="exited with code 1"):
            recorder.record(out, "@DEFAULT_MONITOR@", duration=1)


def test_record_empty_file(tmp_path: Path) -> None:
    out = tmp_path / "out.wav"
    out.touch()  # exists but is empty (0 bytes)

    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.communicate.return_value = (b"", b"")

    with (
        patch("stemforge.capture.recorder.shutil.which", return_value="/usr/bin/parecord"),
        patch("stemforge.capture.recorder.subprocess.Popen", return_value=mock_proc),
        patch("stemforge.capture.recorder.time.sleep"),
    ):
        recorder = AudioRecorder()
        with pytest.raises(CaptureError, match="empty"):
            recorder.record(out, "@DEFAULT_MONITOR@", duration=1)
