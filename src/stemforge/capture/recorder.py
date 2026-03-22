"""System audio recorder using pw-record + pw-link (PipeWire native).

Starts pw-record with no auto-linking (--target 0), then uses pw-link to
explicitly connect the source node's output ports to the capture node's input
ports.  This bypasses sink monitor capture entirely and works regardless of
whether stream.capture.sink is supported by the WirePlumber version.

PipeWire is required; there is no PulseAudio fallback.
"""

import json
import logging
import shutil
import subprocess
import time
from pathlib import Path

from stemforge.exceptions import CaptureError

log = logging.getLogger(__name__)

_CAPTURE_NODE_NAME = "stemforge-capture"

# Native PipeWire rate — avoids any resampling on capture.
# Demucs's convert_audio() will resample to the model's rate later.
_PIPEWIRE_RATE = 48000


class AudioRecorder:
    """Records audio from a PipeWire stream node via explicit pw-link."""

    def record(
        self,
        output_path: Path,
        source: str,
        duration: int,
        sample_rate: int = _PIPEWIRE_RATE,
        channels: int = 2,
    ) -> Path:
        """Capture *duration* seconds from PipeWire node *source*.

        Starts pw-record with no auto-linking, then uses pw-link to connect
        *source*'s output ports directly to the capture node's input ports.

        Args:
            output_path: Destination WAV file (parent directory must exist).
            source: PipeWire node name to capture from (e.g. ``spotify``).
            duration: Recording length in seconds.
            sample_rate: Sample rate in Hz (default: 48000, PipeWire native).
            channels: 1 for mono, 2 for stereo.

        Returns:
            Path to the written WAV file.

        Raises:
            CaptureError: If pw-record/pw-link are unavailable, linking fails,
                or the output file is empty after recording.
        """
        for tool in ("pw-record", "pw-link"):
            if not shutil.which(tool):
                raise CaptureError(
                    f"{tool} not found. PipeWire is required.\n"
                    "  sudo zypper install pipewire  # openSUSE\n"
                    "  sudo apt install pipewire      # Debian/Ubuntu"
                )

        cmd = [
            "pw-record",
            "--target",
            "0",  # no auto-linking — we wire it manually
            "--rate",
            str(sample_rate),
            "--channels",
            str(channels),
            "-P",
            json.dumps({"node.name": _CAPTURE_NODE_NAME}),
            str(output_path),
        ]

        log.info("Recording %d seconds from %r → %s", duration, source, output_path.name)
        log.debug("Command: %s", " ".join(cmd))

        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        except OSError as exc:
            raise CaptureError(f"Failed to launch pw-record: {exc}") from exc

        # Give pw-record time to register its node in the PipeWire graph.
        time.sleep(0.3)

        try:
            _link_nodes(source, _CAPTURE_NODE_NAME)
        except CaptureError:
            proc.terminate()
            proc.communicate(timeout=5)
            raise

        time.sleep(duration)
        proc.terminate()

        try:
            _, stderr_bytes = proc.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
            raise CaptureError("pw-record did not exit cleanly after SIGTERM")

        stderr_text = stderr_bytes.decode(errors="replace").strip()
        if stderr_text:
            log.debug("pw-record stderr: %s", stderr_text)

        if proc.returncode not in (0, 1, -15):  # 0 = clean, 1/-15 = SIGTERM
            raise CaptureError(f"pw-record exited with code {proc.returncode}: {stderr_text}")

        if not output_path.exists() or output_path.stat().st_size == 0:
            raise CaptureError(f"pw-record produced an empty or missing file: {output_path}")

        size_kb = output_path.stat().st_size // 1024
        log.info("Captured %d KB → %s", size_kb, output_path)
        return output_path


def _link_nodes(src_node: str, dst_node: str) -> None:
    """Link *src_node* output ports to *dst_node* input ports via pw-link.

    Discovers port names dynamically from the live PipeWire graph so the
    code is not sensitive to port naming conventions.
    """
    result = subprocess.run(["pw-dump"], capture_output=True, text=True, check=True)
    objects = json.loads(result.stdout)

    # Resolve node names → IDs
    node_ids: dict[str, int] = {
        obj["info"]["props"]["node.name"]: obj["id"]
        for obj in objects
        if obj.get("type") == "PipeWire:Interface:Node"
        and "node.name" in obj.get("info", {}).get("props", {})
    }

    src_id = node_ids.get(src_node)
    dst_id = node_ids.get(dst_node)

    if src_id is None:
        raise CaptureError(
            f"Source node {src_node!r} not found in PipeWire graph.\n"
            "Make sure Spotify is open and playing."
        )
    if dst_id is None:
        raise CaptureError(
            f"Capture node {dst_node!r} not found — pw-record may not have started yet."
        )

    # Collect output ports of src and input ports of dst, sorted for pairing
    src_ports = sorted(
        obj["info"]["props"]["port.name"]
        for obj in objects
        if obj.get("type") == "PipeWire:Interface:Port"
        and obj.get("info", {}).get("props", {}).get("node.id") == src_id
        and obj.get("info", {}).get("direction") == "output"
    )
    dst_ports = sorted(
        obj["info"]["props"]["port.name"]
        for obj in objects
        if obj.get("type") == "PipeWire:Interface:Port"
        and obj.get("info", {}).get("props", {}).get("node.id") == dst_id
        and obj.get("info", {}).get("direction") == "input"
    )

    if not src_ports:
        raise CaptureError(
            f"No output ports found on {src_node!r}. " "Make sure Spotify is actively playing."
        )
    if not dst_ports:
        raise CaptureError(f"No input ports found on capture node {dst_node!r}.")

    log.debug("Linking %s %s → %s %s", src_node, src_ports, dst_node, dst_ports)

    for src_port, dst_port in zip(src_ports, dst_ports):
        subprocess.run(
            ["pw-link", f"{src_node}:{src_port}", f"{dst_node}:{dst_port}"],
            check=True,
            capture_output=True,
        )
        log.debug("Linked %s:%s → %s:%s", src_node, src_port, dst_node, dst_port)
