"""System audio recorder using pw-record (PipeWire native).

Captures audio from a PipeWire monitor node for exactly `duration` seconds
and writes a valid WAV file.

pw-record correctly honours the WAV format header (unlike parecord which
mis-labels the bit-depth when using --fix-format on PipeWire systems).
Falls back to parecord with an explicit s16le format if pw-record is absent.
"""

import logging
import shutil
import subprocess
import time
from pathlib import Path

from stemforge.exceptions import CaptureError

log = logging.getLogger(__name__)

# Native PipeWire rate — avoids any resampling on capture.
# Demucs's convert_audio() will resample to the model's rate later.
_PIPEWIRE_RATE = 48000


class AudioRecorder:
    """Records system audio from a PipeWire monitor node."""

    def record(
        self,
        output_path: Path,
        source: str,
        duration: int,
        sample_rate: int = _PIPEWIRE_RATE,
        channels: int = 2,
    ) -> Path:
        """Capture *duration* seconds of audio from *source* to *output_path*.

        Args:
            output_path: Destination WAV file (parent directory must exist).
            source: PipeWire node target name (e.g. alsa_output.*.monitor).
            duration: Recording length in seconds.
            sample_rate: Sample rate to request (default: 48000, PipeWire native).
            channels: 1 for mono, 2 for stereo.

        Returns:
            Path to the written WAV file.

        Raises:
            CaptureError: If no recorder is available, it fails to start,
                or the output file is empty after recording.
        """
        if shutil.which("pw-record"):
            cmd = self._pw_record_cmd(output_path, source, sample_rate, channels)
            tool = "pw-record"
        elif shutil.which("parecord"):
            log.warning("pw-record not found, falling back to parecord (s16le explicit)")
            cmd = self._parecord_cmd(output_path, source, sample_rate, channels)
            tool = "parecord"
        else:
            raise CaptureError(
                "Neither pw-record nor parecord found.\n"
                "  sudo zypper install pipewire  # openSUSE\n"
                "  sudo apt install pipewire      # Debian/Ubuntu"
            )

        log.info("Recording %d seconds from %r → %s", duration, source, output_path.name)
        log.debug("Command: %s", " ".join(cmd))

        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        except OSError as exc:
            raise CaptureError(f"Failed to launch {tool}: {exc}") from exc

        time.sleep(duration)
        proc.terminate()

        try:
            _, stderr_bytes = proc.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
            raise CaptureError(f"{tool} did not exit cleanly after SIGTERM")

        if proc.returncode not in (0, 1, -15):  # 1 = pw-record SIGTERM, -15 = parecord SIGTERM
            stderr_text = stderr_bytes.decode(errors="replace").strip()
            raise CaptureError(f"{tool} exited with code {proc.returncode}: {stderr_text}")

        if not output_path.exists() or output_path.stat().st_size == 0:
            raise CaptureError(f"{tool} produced an empty or missing file: {output_path}")

        size_kb = output_path.stat().st_size // 1024
        log.info("Captured %d KB → %s", size_kb, output_path)
        return output_path

    @staticmethod
    def _pw_record_cmd(
        output_path: Path, target: str, rate: int, channels: int
    ) -> list[str]:
        return [
            "pw-record",
            "--target", target,
            "--rate", str(rate),
            "--channels", str(channels),
            str(output_path),
        ]

    @staticmethod
    def _parecord_cmd(
        output_path: Path, source: str, rate: int, channels: int
    ) -> list[str]:
        # Explicitly request s16le to avoid the 32-bit header mislabelling bug
        return [
            "parecord",
            f"--device={source}",
            f"--rate={rate}",
            f"--channels={channels}",
            "--format=s16le",
            "--file-format=wav",
            str(output_path),
        ]
