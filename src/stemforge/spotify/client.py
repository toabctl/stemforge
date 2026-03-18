"""Spotify Web API client.

Handles OAuth (PKCE / Authorization Code flow with token caching),
track search, device listing, and playback control.

Prerequisites:
  - A Spotify Premium account
  - An active Spotify client running somewhere (desktop app / web player)
  - App credentials registered at https://developer.spotify.com/dashboard
"""

import logging
import time
from pathlib import Path

import spotipy
from spotipy.oauth2 import SpotifyOAuth

from stemforge.config import Settings
from stemforge.exceptions import (
    NoActiveDeviceError,
    PlaybackError,
    SpotifyAuthError,
    TrackNotFoundError,
)
from stemforge.spotify.models import Device, Track

log = logging.getLogger(__name__)

_SCOPES = " ".join(
    [
        "user-modify-playback-state",
        "user-read-playback-state",
        "user-read-currently-playing",
    ]
)

_TOKEN_CACHE_DIR = Path.home() / ".cache" / "stemforge"


def _make_auth_manager(settings: Settings) -> SpotifyOAuth:
    _TOKEN_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = str(_TOKEN_CACHE_DIR / "token.json")
    return SpotifyOAuth(
        client_id=settings.spotify_client_id,
        client_secret=settings.spotify_client_secret,
        redirect_uri=settings.spotify_redirect_uri,
        scope=_SCOPES,
        cache_path=cache_path,
        open_browser=True,
    )


class SpotifyClient:
    """Thin, typed wrapper around spotipy for the stemforge pipeline."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        try:
            self._sp = spotipy.Spotify(auth_manager=_make_auth_manager(settings))
            # Trigger auth early so any OAuth failure surfaces here
            self._sp.current_user()
        except Exception as exc:
            raise SpotifyAuthError(f"Spotify authentication failed: {exc}") from exc
        log.info("Authenticated with Spotify successfully")

    # ── Search ────────────────────────────────────────────────────────────────

    def search(self, query: str) -> Track:
        """Return the top track result for a free-text search query."""
        log.info("Searching Spotify for: %r", query)
        results = self._sp.search(q=query, type="track", limit=1)
        items = results.get("tracks", {}).get("items", [])
        if not items:
            raise TrackNotFoundError(f"No tracks found for query: {query!r}")

        item = items[0]
        track = Track(
            uri=item["uri"],
            name=item["name"],
            artist=item["artists"][0]["name"],
            duration_ms=item["duration_ms"],
        )
        log.info("Found: %s", track)
        return track

    # ── Devices ───────────────────────────────────────────────────────────────

    def list_devices(self) -> list[Device]:
        """Return all available Spotify Connect devices."""
        data = self._sp.devices()
        return [
            Device(
                id=d["id"],
                name=d["name"],
                type=d["type"],
                is_active=d["is_active"],
                volume_percent=d.get("volume_percent"),
            )
            for d in data.get("devices", [])
        ]

    def get_active_device(
        self,
        preferred_name: str = "",
        retries: int = 5,
        delay: float = 2.0,
    ) -> Device:
        """Return a playback device, retrying up to *retries* times.

        If *preferred_name* is set, selects the first device whose name
        contains that string (case-insensitive). Otherwise falls back to
        the currently active device, or any available device.

        Raises NoActiveDeviceError if no suitable device is found.
        """
        for attempt in range(1, retries + 1):
            devices = self.list_devices()

            if preferred_name:
                needle = preferred_name.lower()
                match = next((d for d in devices if needle in d.name.lower()), None)
                if match:
                    log.info("Using Spotify device: %s (%s)", match.name, match.type)
                    return match
                log.debug(
                    "Device %r not found (attempt %d/%d), retrying…",
                    preferred_name,
                    attempt,
                    retries,
                )
            else:
                active = next((d for d in devices if d.is_active), None)
                if active is None and devices:
                    active = devices[0]
                if active is not None:
                    log.info("Using Spotify device: %s (%s)", active.name, active.type)
                    return active
                log.debug("No device found (attempt %d/%d), retrying…", attempt, retries)

            time.sleep(delay)

        msg = (
            f"Spotify device matching {preferred_name!r} not found."
            if preferred_name
            else "No active Spotify device found."
        )
        raise NoActiveDeviceError(f"{msg} Open the Spotify app and try again.")

    # ── Playback control ──────────────────────────────────────────────────────

    def start_playback(self, track_uri: str, device_id: str) -> None:
        """Start playing a track from the beginning on the given device."""
        log.info("Starting playback: %s on device %s", track_uri, device_id)
        try:
            self._sp.start_playback(device_id=device_id, uris=[track_uri])
        except Exception as exc:
            raise PlaybackError(f"Failed to start playback: {exc}") from exc

    def pause_playback(self, device_id: str) -> None:
        """Pause playback on the given device."""
        log.info("Pausing playback on device %s", device_id)
        try:
            self._sp.pause_playback(device_id=device_id)
        except Exception as exc:
            # Non-fatal: log but don't re-raise — the capture is already done
            log.warning("Could not pause playback: %s", exc)
