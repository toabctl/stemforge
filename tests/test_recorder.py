"""Tests for AudioRecorder."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from stemforge.capture.recorder import AudioRecorder
from stemforge.exceptions import CaptureError


def _make_proc(returncode: int, stderr: bytes = b"") -> MagicMock:
    proc = MagicMock()
    proc.returncode = returncode
    proc.communicate.return_value = (b"", stderr)
    return proc


# ── Tool availability ─────────────────────────────────────────────────────────


def test_record_no_tool_available(tmp_path: Path) -> None:
    with patch("stemforge.capture.recorder.shutil.which", return_value=None):
        recorder = AudioRecorder()
        with pytest.raises(CaptureError, match="pw-record"):
            recorder.record(tmp_path / "out.wav", "spotify", duration=1)


def test_record_uses_pw_record_when_available(tmp_path: Path) -> None:
    out = tmp_path / "out.wav"
    out.write_bytes(b"\x00" * 1024)

    proc = _make_proc(returncode=1)  # pw-record exits 1 on SIGTERM — allowed

    with (
        patch("stemforge.capture.recorder.shutil.which", return_value="/usr/bin/pw-record"),
        patch("stemforge.capture.recorder.subprocess.Popen", return_value=proc) as mock_popen,
        patch("stemforge.capture.recorder._link_nodes"),
        patch("stemforge.capture.recorder.time.sleep"),
    ):
        AudioRecorder().record(out, "spotify", duration=1)

    cmd = mock_popen.call_args[0][0]
    assert cmd[0] == "pw-record"
    assert "--target" in cmd


# ── Return code handling ──────────────────────────────────────────────────────


@pytest.mark.parametrize("code", [0, 1, -15])
def test_record_allowed_return_codes(tmp_path: Path, code: int) -> None:
    """Codes 0, 1 (pw-record SIGTERM), and -15 (parecord SIGTERM) are all OK."""
    out = tmp_path / "out.wav"
    out.write_bytes(b"\x00" * 1024)

    proc = _make_proc(returncode=code)

    with (
        patch("stemforge.capture.recorder.shutil.which", return_value="/usr/bin/pw-record"),
        patch("stemforge.capture.recorder.subprocess.Popen", return_value=proc),
        patch("stemforge.capture.recorder._link_nodes"),
        patch("stemforge.capture.recorder.time.sleep"),
    ):
        result = AudioRecorder().record(out, "spotify", duration=1)

    assert result == out


def test_record_unexpected_exit_code_raises(tmp_path: Path) -> None:
    out = tmp_path / "out.wav"

    proc = _make_proc(returncode=2, stderr=b"some error")

    with (
        patch("stemforge.capture.recorder.shutil.which", return_value="/usr/bin/pw-record"),
        patch("stemforge.capture.recorder.subprocess.Popen", return_value=proc),
        patch("stemforge.capture.recorder._link_nodes"),
        patch("stemforge.capture.recorder.time.sleep"),
    ):
        with pytest.raises(CaptureError, match="exited with code 2"):
            AudioRecorder().record(out, "spotify", duration=1)


# ── Output file validation ────────────────────────────────────────────────────


def test_record_empty_file_raises(tmp_path: Path) -> None:
    out = tmp_path / "out.wav"
    out.touch()  # exists but zero bytes

    proc = _make_proc(returncode=0)

    with (
        patch("stemforge.capture.recorder.shutil.which", return_value="/usr/bin/pw-record"),
        patch("stemforge.capture.recorder.subprocess.Popen", return_value=proc),
        patch("stemforge.capture.recorder._link_nodes"),
        patch("stemforge.capture.recorder.time.sleep"),
    ):
        with pytest.raises(CaptureError, match="empty"):
            AudioRecorder().record(out, "spotify", duration=1)


def test_record_missing_file_raises(tmp_path: Path) -> None:
    out = tmp_path / "out.wav"  # never created

    proc = _make_proc(returncode=0)

    with (
        patch("stemforge.capture.recorder.shutil.which", return_value="/usr/bin/pw-record"),
        patch("stemforge.capture.recorder.subprocess.Popen", return_value=proc),
        patch("stemforge.capture.recorder._link_nodes"),
        patch("stemforge.capture.recorder.time.sleep"),
    ):
        with pytest.raises(CaptureError, match="empty or missing"):
            AudioRecorder().record(out, "spotify", duration=1)


# ── Launch failure ────────────────────────────────────────────────────────────


def test_record_oserror_on_launch(tmp_path: Path) -> None:
    with (
        patch("stemforge.capture.recorder.shutil.which", return_value="/usr/bin/pw-record"),
        patch(
            "stemforge.capture.recorder.subprocess.Popen",
            side_effect=OSError("No such file"),
        ),
    ):
        with pytest.raises(CaptureError, match="Failed to launch"):
            AudioRecorder().record(tmp_path / "out.wav", "spotify", duration=1)
