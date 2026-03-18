"""Shared pytest fixtures."""

import os

import pytest

# Provide dummy Spotify credentials so Settings() can be instantiated in tests
# without a real .env file present.
os.environ.setdefault("SPOTIFY_CLIENT_ID", "test_client_id")
os.environ.setdefault("SPOTIFY_CLIENT_SECRET", "test_client_secret")


@pytest.fixture
def settings():
    from stemforge.config import Settings

    return Settings()
