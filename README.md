# stemforge

Capture a song from Spotify, separate it into stems, and generate MIDI files — all from one command.

```
stemforge run "Daft Punk Get Lucky"
```

```
output/daft-punk-get-lucky-20260318T143022/
├── captured.wav          ← 60s audio capture
├── stems/
│   ├── vocals.wav
│   ├── drums.wav
│   ├── bass.wav
│   └── other.wav
└── midi/
    ├── vocals.mid
    ├── drums.mid
    ├── bass.mid
    └── other.mid
```

## How it works

1. **Search** — finds the track via the Spotify Web API
2. **Capture** — triggers playback on Spotify, discovers the Spotify stream node in the PipeWire graph via `pw-dump`, then records directly from it using `pw-record` + `pw-link` (no sink monitor required)
3. **Separate** — runs [Demucs](https://github.com/facebookresearch/demucs) (`htdemucs_ft` model) to split into vocals / drums / bass / other
4. **Convert** — runs [Basic-Pitch](https://github.com/spotify/basic-pitch) (Spotify Research) on each stem to produce MIDI files

## Requirements

- Linux with **PipeWire** (`pw-record`, `pw-link`, `pw-dump`, `pw-play`)
- A **Spotify Premium** account
- The Spotify desktop app open and playing — the Web API needs an active device
- Spotify volume must be non-zero (capture records the actual output stream)

## Setup

### 1. Install dependencies

```bash
uv sync
```

### 2. Create a Spotify app

1. Go to [developer.spotify.com/dashboard](https://developer.spotify.com/dashboard)
2. Create a new app
3. Under **Redirect URIs**, add: `http://127.0.0.1:8888/callback`
4. Copy your **Client ID** and **Client Secret**

### 3. Configure credentials

```bash
cp .env.example .env
```

Edit `.env`:

```env
SPOTIFY_CLIENT_ID=your_client_id_here
SPOTIFY_CLIENT_SECRET=your_client_secret_here
```

The first time you run a command that talks to Spotify, a browser window will open for OAuth authorization. The token is cached in `~/.cache/stemforge/token.json`.

## Usage

### Full pipeline

```bash
uv run stemforge run "Radiohead Karma Police"
uv run stemforge run "Daft Punk Get Lucky" --duration 45
uv run stemforge run "artist:Joy Division track:Atmosphere" --verbose
```

### Play back stems

```bash
uv run stemforge play                     # latest session, all stems
uv run stemforge play --stem vocals       # single stem only
uv run stemforge play --duration 30       # 30 seconds per stem
uv run stemforge play path/to/session/    # specific session
```

Stems play in order: vocals → other → drums → bass. Press Ctrl+C to skip to the next stem; Ctrl+C twice to quit.

### Check available Spotify devices

```bash
uv run stemforge devices
```

Open the Spotify app first — the pipeline needs an active device. To pin a preferred device:

```env
SPOTIFY_DEVICE_NAME=my-computer
```

### Run individual stages

Separate an existing WAV file:

```bash
uv run stemforge separate path/to/audio.wav --output path/to/stems/
```

Convert a single stem to MIDI:

```bash
uv run stemforge convert path/to/stems/vocals.wav
```

## Configuration

All settings can be set in `.env` or as environment variables:

| Variable | Default | Description |
|---|---|---|
| `SPOTIFY_CLIENT_ID` | *(required)* | Spotify app Client ID |
| `SPOTIFY_CLIENT_SECRET` | *(required)* | Spotify app Client Secret |
| `SPOTIFY_REDIRECT_URI` | `http://127.0.0.1:8888/callback` | OAuth redirect URI |
| `SPOTIFY_DEVICE_NAME` | *(auto)* | Preferred Spotify device name (partial match) |
| `PIPEWIRE_SINK` | *(auto-discovered)* | PipeWire stream node name to capture from; leave empty to auto-detect |
| `CAPTURE_DURATION_SECONDS` | `60` | Recording length in seconds (5–300) |
| `CAPTURE_SAMPLE_RATE` | `44100` | Sample rate in Hz |
| `CAPTURE_CHANNELS` | `2` | Channels (1=mono, 2=stereo) |
| `DEMUCS_MODEL` | `htdemucs_ft` | Demucs model name |
| `DEMUCS_DEVICE` | `cpu` | `cpu`, `cuda`, or `mps` |
| `DEMUCS_SHIFTS` | `2` | Random shifts for quality (higher = slower) |
| `MIDI_ONSET_THRESHOLD` | `0.3` | Note onset sensitivity (lower = more notes) |
| `MIDI_FRAME_THRESHOLD` | `0.1` | Note frame sensitivity (lower = more notes) |
| `MIDI_MIN_NOTE_LENGTH` | `127.7` | Minimum note length in milliseconds |
| `PLAYBACK_START_DELAY_SECONDS` | `3.0` | Wait after play command before recording |
| `OUTPUT_DIR` | `output` | Base directory for session output |

## Development

```bash
# Run tests
uv run pytest

# Lint
uv run ruff check src/ tests/

# Type check
uv run mypy src/

# Run all checks via tox
uv run tox
```

## Notes

- Stem separation is CPU-bound and takes a few minutes without a GPU. Set `DEMUCS_DEVICE=cuda` if you have one.
- MIDI quality is best on melodic content (vocals, bass, lead instruments). Drums produce rhythm patterns rather than pitched notes.
- Spotify volume must not be zero — the capture records the actual audio stream sent to PipeWire.
- Auto-discovery polls PipeWire every 0.5 s for up to `PLAYBACK_START_DELAY_SECONDS` waiting for Spotify's stream node to appear. If discovery fails, set `PIPEWIRE_SINK` explicitly to the node name shown by `pw-dump`.
