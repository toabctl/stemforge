"""MIDI converter using Basic-Pitch (Spotify Research).

Uses the ONNX backend for inference — same ICASSP 2022 model weights as the
TensorFlow backend but faster and without the TF startup overhead.

Per-stem optimisations applied:
  - Stems are peak-normalised before inference so quiet stems aren't missed
  - multiple_pitch_bends enabled for expressive slides/vibrato

Reference: https://github.com/spotify/basic-pitch
"""

import logging
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf

from stemforge.config import Settings
from stemforge.exceptions import ConversionError

log = logging.getLogger(__name__)


def _get_onnx_model_path() -> Path:
    """Return the ONNX model path, falling back to TF SavedModel if needed."""
    try:
        from basic_pitch import FilenameSuffix, build_icassp_2022_model_path

        onnx_path = build_icassp_2022_model_path(FilenameSuffix.onnx)
        if onnx_path.exists():
            return onnx_path
        return build_icassp_2022_model_path(FilenameSuffix.tf)
    except Exception:
        from basic_pitch import ICASSP_2022_MODEL_PATH

        return Path(ICASSP_2022_MODEL_PATH)


def _normalize_wav(src: Path, dst: Path) -> None:
    """Peak-normalise *src* to 0 dBFS and write to *dst*.

    Quiet stems (e.g. a sparse bass line) can fall below Basic-Pitch's
    effective detection threshold. Normalising ensures the model always
    receives a full-amplitude signal regardless of mix level.
    """
    data, sr = sf.read(str(src), always_2d=True)
    peak = np.abs(data).max()
    if peak > 0:
        data = data / peak * 0.99  # leave 1% headroom to avoid clipping
    sf.write(str(dst), data, sr)


class MidiConverter:
    """Converts WAV stems to MIDI using Basic-Pitch (ONNX backend)."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._model = self._load_model()

    # ── Public API ─────────────────────────────────────────────────────────

    def convert(self, stem_wav: Path, output_dir: Path, stem_name: str) -> Path:
        """Convert *stem_wav* to a MIDI file in *output_dir*.

        Applies peak normalisation and pitch-bend capture before running
        Basic-Pitch inference.

        Returns:
            Path to the written MIDI file.

        Raises:
            ConversionError: If Basic-Pitch inference or MIDI write fails.
        """
        from basic_pitch.inference import predict

        out_path = output_dir / f"{stem_name}.mid"

        log.info("Converting %s → %s", stem_wav.name, out_path.name)

        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp_path = Path(tmp.name)

            _normalize_wav(stem_wav, tmp_path)

            _, midi_data, _ = predict(
                str(tmp_path),
                self._model,
                onset_threshold=self._settings.midi_onset_threshold,
                frame_threshold=self._settings.midi_frame_threshold,
                minimum_note_length=self._settings.midi_min_note_length,
                multiple_pitch_bends=True,
            )
            midi_data.write(str(out_path))
        except Exception as exc:
            raise ConversionError(f"Basic-Pitch failed on {stem_wav.name}: {exc}") from exc
        finally:
            tmp_path.unlink(missing_ok=True)

        if not out_path.exists() or out_path.stat().st_size == 0:
            raise ConversionError(f"MIDI output is empty: {out_path}")

        size_bytes = out_path.stat().st_size
        log.info("Wrote MIDI (%d bytes): %s", size_bytes, out_path.name)
        return out_path

    def convert_all(self, stem_paths: dict[str, Path], output_dir: Path) -> dict[str, Path]:
        """Convert every stem, skipping individual failures gracefully."""
        midi_paths: dict[str, Path] = {}
        for name, wav_path in stem_paths.items():
            try:
                midi_paths[name] = self.convert(wav_path, output_dir, name)
            except ConversionError as exc:
                log.warning("Skipping MIDI conversion for %r: %s", name, exc)
        return midi_paths

    # ── Internal helpers ───────────────────────────────────────────────────

    @staticmethod
    def _load_model():
        try:
            from basic_pitch.inference import Model

            model_path = _get_onnx_model_path()
            log.info("Loading Basic-Pitch ONNX model from %s…", model_path)
            return Model(model_path)
        except Exception as exc:
            raise ConversionError(f"Failed to load Basic-Pitch model: {exc}") from exc
