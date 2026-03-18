# stemforge

Capture a song from Spotify, separate it into stems, and generate MIDI files — all from one command.

```
stemforge run "Daft Punk Get Lucky"
```

```
output/daft-punk-get-lucky-20260318T143022/
├── captured.wav          ← 30s system audio capture
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
2. **Capture** — triggers playback, waits for buffering, then records system audio via `parecord` (PulseAudio/PipeWire monitor source)
3. **Separate** — runs [Demucs](https://github.com/facebookresearch/demucs) (`htdemucs` model) to split into vocals / drums / bass / other
4. **Convert** — runs [Basic-Pitch](https://github.com/spotify/basic-pitch) (Spotify Research) on each stem to produce MIDI files

## Requirements

- Linux with PulseAudio or PipeWire
- `parecord` (`pulseaudio-utils` package)
- A **Spotify Premium** account
- The Spotify desktop app (or web player) open and playing — the Web API needs an active device

## Setup

### 1. Install dependencies

```bash
uv sync
```

### 2. Create a Spotify app

1. Go to [developer.spotify.com/dashboard](https://developer.spotify.com/dashboard)
2. Create a new app
3. Under **Redirect URIs**, add: `http://localhost:8888/callback`
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

### Check available Spotify devices

```bash
uv run stemforge devices
```

Open the Spotify app first — the pipeline needs an active device.

### Check available monitor sources

```bash
uv run stemforge sources
```

By default `@DEFAULT_MONITOR@` is used (auto-detected). To pin a specific source:

```env
PULSE_MONITOR_SOURCE=alsa_output.pci-0000_07_00.6.analog-stereo.monitor
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
| `SPOTIFY_REDIRECT_URI` | `http://localhost:8888/callback` | OAuth redirect URI |
| `PULSE_MONITOR_SOURCE` | `@DEFAULT_MONITOR@` | PulseAudio/PipeWire monitor source |
| `CAPTURE_DURATION_SECONDS` | `30` | Recording length in seconds |
| `DEMUCS_MODEL` | `htdemucs` | Demucs model name |
| `DEMUCS_DEVICE` | `cpu` | `cpu`, `cuda`, or `mps` |
| `DEMUCS_SHIFTS` | `1` | Random shifts for quality (higher = slower) |
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
```

## Notes

- Stem separation is CPU-bound and takes a few minutes without a GPU. Set `DEMUCS_DEVICE=cuda` if you have one.
- MIDI quality is best on melodic content (vocals, bass, lead instruments). Drums produce rhythm patterns rather than pitched notes.
- The capture relies on the song actually playing through your system audio. Make sure your Spotify volume is not muted.
