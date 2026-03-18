"""Stem separator using Demucs.

Uses the Demucs programmatic API (not its CLI / subprocess) so that the
model is loaded once and reused across multiple files, and so that errors
surface as Python exceptions rather than sys.exit() calls.

Model output tensor shape: (sources, channels, samples)
Model source names: ["drums", "bass", "other", "vocals"] (htdemucs)
"""

import logging
from pathlib import Path

import torch

from stemforge.config import Settings
from stemforge.exceptions import SeparationError

log = logging.getLogger(__name__)


class StemSeparator:
    """Loads a Demucs model once and separates audio files on demand."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._device = self._resolve_device(settings.demucs_device)
        self._model = self._load_model(settings.demucs_model, self._device)

    # ── Public API ─────────────────────────────────────────────────────────

    def separate(self, input_wav: Path, output_dir: Path) -> dict[str, Path]:
        """Separate *input_wav* into stems and write each to *output_dir*.

        Returns:
            Mapping of stem name → path to the written WAV file.
            e.g. {"vocals": Path(".../vocals.wav"), "drums": Path(...), …}
        """
        import soundfile as sf

        from demucs.apply import apply_model
        from demucs.audio import convert_audio

        log.info("Loading audio: %s", input_wav)
        # Use soundfile to avoid torchaudio's torchcodec dependency
        data, sr = sf.read(str(input_wav), always_2d=True)  # (samples, channels)
        wav = torch.from_numpy(data.T).float()              # (channels, samples)

        # Demucs expects (batch, channels, samples) at the model's native rate
        wav = convert_audio(
            wav,
            sr,
            self._model.samplerate,
            self._model.audio_channels,
        )
        wav = wav.unsqueeze(0).to(self._device)  # add batch dim

        log.info(
            "Separating stems with %s on %s (shifts=%d)…",
            self._settings.demucs_model,
            self._device,
            self._settings.demucs_shifts,
        )

        try:
            with torch.no_grad():
                sources = apply_model(
                    self._model,
                    wav,
                    shifts=self._settings.demucs_shifts,
                    device=self._device,
                    progress=True,
                )
        except Exception as exc:
            raise SeparationError(f"Demucs inference failed: {exc}") from exc

        # sources shape: (batch=1, n_sources, channels, samples)
        sources = sources[0]  # remove batch dim → (n_sources, channels, samples)
        stem_paths: dict[str, Path] = {}

        for idx, name in enumerate(self._model.sources):
            stem_tensor = sources[idx]  # (channels, samples)
            out_path = output_dir / f"{name}.wav"
            audio_np = stem_tensor.cpu().numpy().T  # (samples, channels)
            sf.write(str(out_path), audio_np, self._model.samplerate)
            log.info("Wrote stem: %s", out_path.name)
            stem_paths[name] = out_path

        return stem_paths

    # ── Internal helpers ───────────────────────────────────────────────────

    @staticmethod
    def _resolve_device(requested: str) -> str:
        if requested == "cuda" and not torch.cuda.is_available():
            log.warning("CUDA not available, falling back to CPU")
            return "cpu"
        if requested == "mps" and not torch.backends.mps.is_available():
            log.warning("MPS not available, falling back to CPU")
            return "cpu"
        return requested

    @staticmethod
    def _load_model(model_name: str, device: str):
        from demucs.pretrained import get_model

        log.info("Loading Demucs model %r on %s…", model_name, device)
        try:
            model = get_model(model_name)
            model.to(device)
            model.eval()
            return model
        except Exception as exc:
            raise SeparationError(
                f"Failed to load Demucs model {model_name!r}: {exc}"
            ) from exc
