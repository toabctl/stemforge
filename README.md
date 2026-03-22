# stemforge

Capture a song from Spotify, separate it into stems, and generate MIDI files — all from one command.

```
stemforge run "Gerry Mulligan Lines for Lyons"
```

```
output/gerry-mulligan-lines-for-lyons/
├── captured.wav
├── stems/
│   ├── vocals.wav
│   ├── guitar.wav
│   ├── piano.wav
│   ├── drums.wav
│   ├── bass.wav
│   └── other.wav
└── midi/
    ├── vocals.mid
    ├── guitar.mid
    ├── piano.mid
    ├── drums.mid
    ├── bass.mid
    └── other.mid
```

## How it works

1. **Record** — finds the track via the Spotify Web API, triggers playback, discovers the stream node in the PipeWire graph via `pw-dump`, and records directly from it using `pw-record` + `pw-link`
2. **Split** — runs [Demucs](https://github.com/facebookresearch/demucs) (`htdemucs_6s`) to split into vocals / drums / bass / guitar / piano / other
3. **MIDI** — runs [Basic-Pitch](https://github.com/spotify/basic-pitch) (Spotify Research) on each stem to produce MIDI files

## Requirements

- Linux with **PipeWire** (`pw-record`, `pw-link`, `pw-dump`, `pw-play`)
- A **Spotify Premium** account
- The Spotify desktop app open and playing — the Web API needs an active device

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
stemforge run "Gerry Mulligan Lines for Lyons"
stemforge run "Gerry Mulligan Lines for Lyons" --start 10 --duration 45
```

### Individual stages

Record a Spotify track to WAV only:

```bash
stemforge record "Gerry Mulligan Lines for Lyons"
stemforge record "Gerry Mulligan Lines for Lyons" --start 30 --duration 60
```

Split an existing WAV into stems:

```bash
stemforge split output/gerry-mulligan-lines-for-lyons/captured.wav
stemforge split captured.wav --model htdemucs_ft    # use 4-stem model instead
```

Convert stems to MIDI (single file or directory):

```bash
stemforge midi output/gerry-mulligan-lines-for-lyons/stems/
stemforge midi output/gerry-mulligan-lines-for-lyons/stems/piano.wav
```

### Play back stems

```bash
stemforge play                          # latest session, all stems
stemforge play --stem piano             # single stem only
stemforge play --duration 30            # 30 seconds per stem
stemforge play output/gerry-mulligan-lines-for-lyons/
```

Stems play in order: vocals → guitar → piano → other → drums → bass. Press Ctrl+C to skip; Ctrl+C twice to quit.

### Diagnostics

```bash
stemforge info devices                  # list Spotify Connect devices
stemforge info streams                  # list PipeWire audio output streams
```

## Configuration

All settings can be set in `.env` or as environment variables. Only `SPOTIFY_CLIENT_ID` and `SPOTIFY_CLIENT_SECRET` are required — everything else has sensible defaults.

| Variable | Default | Description |
|---|---|---|
| `SPOTIFY_CLIENT_ID` | *(required)* | Spotify app Client ID |
| `SPOTIFY_CLIENT_SECRET` | *(required)* | Spotify app Client Secret |
| `SPOTIFY_REDIRECT_URI` | `http://127.0.0.1:8888/callback` | OAuth redirect URI |
| `SPOTIFY_DEVICE_NAME` | *(auto)* | Preferred Spotify device name (partial match) |
| `PIPEWIRE_SINK` | *(auto)* | PipeWire stream node name; leave empty to auto-detect |
| `CAPTURE_DURATION_SECONDS` | `60` | Recording length in seconds (5–300) |
| `CAPTURE_SAMPLE_RATE` | `44100` | Sample rate in Hz |
| `CAPTURE_CHANNELS` | `2` | Channels (1=mono, 2=stereo) |
| `DEMUCS_MODEL` | `htdemucs_6s` | Demucs model name |
| `DEMUCS_DEVICE` | `cpu` | `cpu`, `cuda`, or `mps` |
| `DEMUCS_SHIFTS` | `2` | Random shifts for quality (higher = slower) |
| `MIDI_ONSET_THRESHOLD` | `0.5` | Note onset sensitivity (lower = more notes) |
| `MIDI_FRAME_THRESHOLD` | `0.3` | Note frame sensitivity (lower = more notes) |
| `MIDI_MIN_NOTE_LENGTH` | `127.7` | Minimum note length in milliseconds |
| `PLAYBACK_START_DELAY_SECONDS` | `3.0` | Wait for Spotify stream node to appear |
| `OUTPUT_DIR` | `output` | Base directory for session output |

## Development

```bash
uv run pytest           # run tests
uv run tox              # run all checks (lint + tests)
```

## Notes

- Stem separation is CPU-bound and takes a few minutes without a GPU. Set `DEMUCS_DEVICE=cuda` if you have one.
- MIDI quality is best on melodic content (vocals, bass, guitar, piano). Drums produce rhythm patterns rather than pitched notes.
- Spotify volume must not be zero — the capture records the actual audio stream sent to PipeWire.
- Auto-discovery polls PipeWire every 0.5 s for up to `PLAYBACK_START_DELAY_SECONDS` waiting for Spotify's stream node to appear. If discovery fails, set `PIPEWIRE_SINK` explicitly — use `stemforge info streams` to find the node name.
