"""Tests for filesystem utilities."""

from pathlib import Path

import pytest

from stemforge.utils.fs import _slugify, build_session_paths


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Hello World", "hello-world"),
        ("AC/DC", "ac-dc"),
        ("Björk", "bjork"),
        ("  leading/trailing  ", "leading-trailing"),
        ("a" * 100, "a" * 40),
    ],
)
def test_slugify(text: str, expected: str) -> None:
    assert _slugify(text) == expected


def test_build_session_paths_creates_dirs(tmp_path: Path) -> None:
    paths = build_session_paths(tmp_path, "Daft Punk", "Get Lucky")

    assert paths.session_dir.exists()
    assert paths.stems_dir.exists()
    assert paths.midi_dir.exists()
    assert paths.session_dir.name == "daft-punk-get-lucky"


def test_build_session_paths_overwrites_existing(tmp_path: Path) -> None:
    paths = build_session_paths(tmp_path, "Daft Punk", "Get Lucky")
    stale_file = paths.stems_dir / "old.wav"
    stale_file.touch()

    paths2 = build_session_paths(tmp_path, "Daft Punk", "Get Lucky")
    assert paths2.session_dir.exists()
    assert not (paths2.stems_dir / "old.wav").exists()


def test_session_paths_stem_helpers(tmp_path: Path) -> None:
    paths = build_session_paths(tmp_path, "Artist", "Title")
    assert paths.stem_wav("vocals").name == "vocals.wav"
    assert paths.stem_midi("drums").name == "drums.mid"
