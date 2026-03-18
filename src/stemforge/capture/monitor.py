"""PulseAudio/PipeWire monitor source discovery.

On systems running PipeWire with a PulseAudio compatibility layer the
source names are stable (e.g. alsa_output.pci-0000_07_00.6.analog-stereo.monitor)
even though the numeric IDs change across reboots.

The @DEFAULT_MONITOR@ alias is supported natively by parecord and is the
safe fallback when explicit source discovery fails.
"""

import logging
import subprocess

from stemforge.exceptions import MonitorSourceError

log = logging.getLogger(__name__)


def get_default_monitor_source() -> str:
    """Resolve the monitor source name for the current default audio sink.

    Returns the explicit `.monitor` source name if discoverable, otherwise
    falls back to `@DEFAULT_MONITOR@` (recognised by parecord built-in).
    """
    try:
        sink_name = _get_default_sink()
        monitor_name = f"{sink_name}.monitor"
        if _source_exists(monitor_name):
            log.debug("Resolved monitor source: %s", monitor_name)
            return monitor_name
        log.debug(
            "Monitor source %r not found in source list, using @DEFAULT_MONITOR@",
            monitor_name,
        )
    except Exception as exc:
        log.debug("Source discovery failed (%s), using @DEFAULT_MONITOR@", exc)

    return "@DEFAULT_MONITOR@"


def list_monitor_sources() -> list[str]:
    """Return all `.monitor` source names visible to PulseAudio/PipeWire."""
    try:
        out = subprocess.check_output(
            ["pactl", "list", "sources", "short"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        raise MonitorSourceError(f"pactl not available or failed: {exc}") from exc

    return [
        parts[1]
        for line in out.splitlines()
        if (parts := line.split()) and len(parts) >= 2 and ".monitor" in parts[1]
    ]


def _get_default_sink() -> str:
    out = subprocess.check_output(
        ["pactl", "get-default-sink"],
        text=True,
        stderr=subprocess.DEVNULL,
    )
    return out.strip()


def _source_exists(name: str) -> bool:
    sources = list_monitor_sources()
    return name in sources
