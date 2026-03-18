"""Typer CLI for stemforge.

Commands:
  run       Full pipeline: search → capture → separate → MIDI
  play      Play separated stems from a session (default: latest)
  devices   List available Spotify Connect devices
  sources   List PulseAudio/PipeWire monitor sources
  separate  Run stem separation on an existing WAV file
  convert   Run MIDI conversion on an existing stem WAV file
"""

import shutil
import subprocess
import sys
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich import print as rprint
from rich.console import Console
from rich.table import Table

from stemforge.config import Settings
from stemforge.exceptions import StemforgeError
from stemforge.utils.logging import configure_logging

app = typer.Typer(
    name="stemforge",
    help="Capture Spotify audio, separate stems, and generate MIDI files.",
    add_completion=False,
    pretty_exceptions_show_locals=False,
)
console = Console()
err_console = Console(stderr=True, style="bold red")


# ── Shared options ────────────────────────────────────────────────────────────

VerboseOpt = Annotated[bool, typer.Option("--verbose", "-v", help="Enable debug logging")]
QuietOpt = Annotated[bool, typer.Option("--quiet", "-q", help="Suppress info logging")]


def _load_settings() -> Settings:
    try:
        return Settings()
    except Exception as exc:
        err_console.print(f"[bold red]Configuration error:[/] {exc}")
        err_console.print("Copy [cyan].env.example[/] to [cyan].env[/] and fill in your credentials.")
        raise typer.Exit(code=1)


# ── run command ───────────────────────────────────────────────────────────────

@app.command()
def run(
    query: Annotated[str, typer.Argument(help="Track search query (artist, title, or both)")],
    duration: Annotated[
        Optional[int],
        typer.Option("--duration", "-d", help="Override capture duration in seconds"),
    ] = None,
    verbose: VerboseOpt = False,
    quiet: QuietOpt = False,
) -> None:
    """Run the full pipeline: search → capture → separate stems → generate MIDI."""
    configure_logging(verbose=verbose, quiet=quiet)
    settings = _load_settings()

    rprint(f"\n[bold cyan]stemforge[/] — starting pipeline for [green]{query!r}[/]\n")

    try:
        from stemforge.pipeline import Pipeline

        pipeline = Pipeline(settings)
        result = pipeline.run(query, duration=duration)
    except StemforgeError as exc:
        err_console.print(f"\n[bold red]Pipeline failed:[/] {exc}")
        raise typer.Exit(code=2)
    except KeyboardInterrupt:
        rprint("\n[yellow]Aborted by user.[/]")
        raise typer.Exit(code=130)

    # ── Summary table ──────────────────────────────────────────────────────
    rprint(f"\n[bold green]Done![/] Track: {result.track}\n")

    table = Table(title="Output Files", show_header=True, header_style="bold magenta")
    table.add_column("Type", style="cyan", no_wrap=True)
    table.add_column("File", style="white")
    table.add_column("Size", justify="right", style="dim")

    def _size(p: Path) -> str:
        if not p.exists():
            return "?"
        b = p.stat().st_size
        return f"{b / 1024:.1f} KB" if b >= 1024 else f"{b} B"

    table.add_row("Capture", str(result.captured_wav), _size(result.captured_wav))
    for name, path in sorted(result.stem_paths.items()):
        table.add_row(f"Stem ({name})", str(path), _size(path))
    for name, path in sorted(result.midi_paths.items()):
        table.add_row(f"MIDI ({name})", str(path), _size(path))

    console.print(table)
    rprint(f"\n[dim]Session directory: {result.session.session_dir}[/]")


# ── play command ─────────────────────────────────────────────────────────────

@app.command()
def play(
    session: Annotated[
        Optional[Path],
        typer.Argument(help="Session directory to play (default: latest in output/)"),
    ] = None,
    stem: Annotated[
        Optional[str],
        typer.Option("--stem", "-s", help="Play a single stem only (vocals/drums/bass/other)"),
    ] = None,
    duration: Annotated[
        Optional[int],
        typer.Option("--duration", "-d", help="Seconds to play per stem (0 = full length)"),
    ] = 15,
) -> None:
    """Play separated stems from a session. Defaults to the most recent run.

    Controls:
      Ctrl+C once  → skip to next stem
      Ctrl+C twice → quit
    """
    if shutil.which("paplay") is None:
        err_console.print("[bold red]paplay not found.[/] Install pulseaudio-utils.")
        raise typer.Exit(code=1)

    session_dir = session or _latest_session(_load_settings().output_dir)
    if session_dir is None:
        err_console.print("No sessions found. Run [cyan]stemforge run[/] first.")
        raise typer.Exit(code=1)

    stems_dir = session_dir / "stems"
    if not stems_dir.exists():
        err_console.print(f"No stems directory found in {session_dir}")
        raise typer.Exit(code=1)

    stem_order = ["vocals", "drums", "bass", "other"]
    wav_files: list[Path] = []

    if stem:
        p = stems_dir / f"{stem}.wav"
        if not p.exists():
            err_console.print(f"Stem [cyan]{stem}.wav[/] not found in {stems_dir}")
            raise typer.Exit(code=1)
        wav_files = [p]
    else:
        # Play in a musically logical order; include any unexpected stems too
        known = [stems_dir / f"{s}.wav" for s in stem_order if (stems_dir / f"{s}.wav").exists()]
        extra = sorted(p for p in stems_dir.glob("*.wav") if p not in known)
        wav_files = known + extra

    if not wav_files:
        err_console.print(f"No WAV files found in {stems_dir}")
        raise typer.Exit(code=1)

    limit = duration or None
    dur_label = f"{limit}s" if limit else "full"
    rprint(f"\n[bold cyan]Playing stems[/] from [dim]{session_dir.name}[/] [dim]({dur_label} each)[/]")
    rprint("[dim]Ctrl+C to skip · Ctrl+C twice to quit[/]\n")

    for wav in wav_files:
        rprint(f"  ▶  [bold green]{wav.stem}[/]")
        try:
            proc = subprocess.Popen(
                ["paplay", str(wav)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            try:
                proc.wait(timeout=limit)
            except subprocess.TimeoutExpired:
                proc.terminate()
                proc.wait()
        except KeyboardInterrupt:
            proc.terminate()
            proc.wait()
            rprint("  [yellow]skipped[/]")
            try:
                # Brief window: a second Ctrl+C quits entirely
                import time; time.sleep(0.3)
            except KeyboardInterrupt:
                rprint("\n[yellow]Stopped.[/]")
                raise typer.Exit(code=0)

    rprint("\n[dim]Done.[/]")


def _latest_session(output_dir: Path) -> Optional[Path]:
    """Return the most recently created session directory."""
    if not output_dir.exists():
        return None
    sessions = sorted(
        (p for p in output_dir.iterdir() if p.is_dir()),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return sessions[0] if sessions else None


# ── devices command ───────────────────────────────────────────────────────────

@app.command()
def devices(
    verbose: VerboseOpt = False,
) -> None:
    """List available Spotify Connect playback devices."""
    configure_logging(verbose=verbose)
    settings = _load_settings()

    try:
        from stemforge.spotify.client import SpotifyClient

        client = SpotifyClient(settings)
        device_list = client.list_devices()
    except StemforgeError as exc:
        err_console.print(f"[bold red]Error:[/] {exc}")
        raise typer.Exit(code=2)

    if not device_list:
        rprint("[yellow]No Spotify devices found. Open the Spotify app and try again.[/]")
        raise typer.Exit(code=1)

    table = Table(title="Spotify Devices", header_style="bold magenta")
    table.add_column("Name", style="cyan")
    table.add_column("Type")
    table.add_column("Active", justify="center")
    table.add_column("Volume", justify="right", style="dim")

    for d in device_list:
        table.add_row(
            d.name,
            d.type,
            "[green]✓[/]" if d.is_active else "",
            f"{d.volume_percent}%" if d.volume_percent is not None else "—",
        )

    console.print(table)


# ── sources command ───────────────────────────────────────────────────────────

@app.command()
def sources() -> None:
    """List PulseAudio/PipeWire monitor sources available for audio capture."""
    try:
        from stemforge.capture.monitor import list_monitor_sources
        from stemforge.exceptions import MonitorSourceError

        monitor_sources = list_monitor_sources()
    except Exception as exc:
        err_console.print(f"[bold red]Error:[/] {exc}")
        raise typer.Exit(code=2)

    if not monitor_sources:
        rprint("[yellow]No monitor sources found. Is PulseAudio/PipeWire running?[/]")
        raise typer.Exit(code=1)

    table = Table(title="Monitor Sources", header_style="bold magenta")
    table.add_column("Source Name", style="cyan")

    for s in monitor_sources:
        table.add_row(s)

    console.print(table)
    rprint("\n[dim]Set PULSE_MONITOR_SOURCE=<name> in .env to use a specific source.[/]")


# ── separate command ──────────────────────────────────────────────────────────

@app.command()
def separate(
    wav_file: Annotated[Path, typer.Argument(help="Path to input WAV file")],
    output_dir: Annotated[
        Optional[Path],
        typer.Option("--output", "-o", help="Output directory (default: next to WAV)"),
    ] = None,
    verbose: VerboseOpt = False,
) -> None:
    """Run stem separation on an existing WAV file (skips capture stage)."""
    configure_logging(verbose=verbose)
    settings = _load_settings()

    if not wav_file.exists():
        err_console.print(f"File not found: {wav_file}")
        raise typer.Exit(code=1)

    stems_dir = output_dir or wav_file.parent / "stems"
    stems_dir.mkdir(parents=True, exist_ok=True)

    try:
        from stemforge.separation.separator import StemSeparator

        separator = StemSeparator(settings)
        stem_paths = separator.separate(wav_file, stems_dir)
    except StemforgeError as exc:
        err_console.print(f"[bold red]Separation failed:[/] {exc}")
        raise typer.Exit(code=2)

    rprint(f"\n[bold green]Stems written to:[/] {stems_dir}\n")
    for name, path in sorted(stem_paths.items()):
        rprint(f"  [cyan]{name}[/] → {path}")


# ── convert command ───────────────────────────────────────────────────────────

@app.command()
def convert(
    wav_file: Annotated[Path, typer.Argument(help="Path to stem WAV file")],
    output_dir: Annotated[
        Optional[Path],
        typer.Option("--output", "-o", help="Output directory (default: next to WAV)"),
    ] = None,
    stem_name: Annotated[
        Optional[str],
        typer.Option("--name", "-n", help="Stem name (used as output filename)"),
    ] = None,
    verbose: VerboseOpt = False,
) -> None:
    """Convert a single stem WAV file to MIDI using Basic-Pitch."""
    configure_logging(verbose=verbose)

    if not wav_file.exists():
        err_console.print(f"File not found: {wav_file}")
        raise typer.Exit(code=1)

    midi_dir = output_dir or wav_file.parent
    midi_dir.mkdir(parents=True, exist_ok=True)
    name = stem_name or wav_file.stem

    try:
        from stemforge.midi.converter import MidiConverter

        converter = MidiConverter()
        midi_path = converter.convert(wav_file, midi_dir, name)
    except StemforgeError as exc:
        err_console.print(f"[bold red]Conversion failed:[/] {exc}")
        raise typer.Exit(code=2)

    rprint(f"\n[bold green]MIDI written:[/] {midi_path}")


# ── entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    app()


if __name__ == "__main__":
    main()
