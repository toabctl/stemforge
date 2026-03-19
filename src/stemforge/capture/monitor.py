"""PipeWire Spotify stream node discovery.

Uses ``pw-dump`` to find the active Spotify output stream node.  The node
name is passed to the recorder, which uses ``pw-link`` to connect it directly
to the capture node — no sink monitor capture required.
"""

import json
import logging
import subprocess

log = logging.getLogger(__name__)

_PW_NODE = "PipeWire:Interface:Node"


def get_spotify_monitor_source() -> str | None:
    """Return the PipeWire stream node name for the active Spotify output.

    Looks for a ``Stream/Output/Audio`` node whose ``node.name``,
    ``application.name``, or ``application.process.binary`` contains
    "spotify".

    Returns ``None`` if no active Spotify stream is found.
    """
    try:
        objects = _pw_dump()
        spotify_ids = _find_spotify_node_ids(objects)
        if not spotify_ids:
            log.debug("No active Spotify stream nodes found in PipeWire graph")
            return None
        for obj in objects:
            if obj.get("type") == _PW_NODE and obj["id"] in spotify_ids:
                name = obj.get("info", {}).get("props", {}).get("node.name")
                if name:
                    log.info("Found Spotify stream node: %s", name)
                    return name
        log.debug("Spotify node found by ID but has no node.name")
    except Exception as exc:
        log.debug("Spotify node discovery failed (%s)", exc)
    return None


# ── Internal helpers ──────────────────────────────────────────────────────────


def _pw_dump() -> list[dict]:
    out = subprocess.check_output(
        ["pw-dump"],
        text=True,
        stderr=subprocess.DEVNULL,
    )
    return json.loads(out)


def _find_spotify_node_ids(objects: list[dict]) -> set[int]:
    """Return node IDs of active Spotify output stream nodes.

    Matches on node.name, application.name, or application.process.binary
    because Spotify (flatpak/pipewire-pulse) puts application identity on the
    Client object rather than the Node.
    """
    ids: set[int] = set()
    for obj in objects:
        if obj.get("type") != _PW_NODE:
            continue
        props = obj.get("info", {}).get("props", {})
        if props.get("media.class") != "Stream/Output/Audio":
            continue
        if any(
            "spotify" in props.get(key, "").lower()
            for key in ("node.name", "application.name", "application.process.binary")
        ):
            ids.add(obj["id"])
    return ids
