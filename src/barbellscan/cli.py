"""Kommandozeile. Weitere Befehle (simulate, track, ...) folgen in M1-M7."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import typer

from . import __version__
from .config import load_analysis, load_bars
from .manifest import check_manifest, expected_design

app = typer.Typer(help="Barbellscan: Durchbiegungsanalyse von Langhanteln", no_args_is_help=True)


@app.command()
def version() -> None:
    """Version ausgeben."""
    typer.echo(__version__)


@app.command()
def design(
    bars: Path = Path("config/bars.yaml"),
    analysis: Path = Path("config/analysis.yaml"),
) -> None:
    """Studiendesign aus der Config zusammenfassen (Stangen, Bilder)."""
    catalog, cfg = load_bars(bars), load_analysis(analysis)
    n_bars = len(catalog.bar_ids())
    total = len(expected_design(catalog, cfg))
    typer.echo(f"Modelle: {len(catalog.bars)}, physische Stangen: {n_bars}")
    typer.echo(f"Laststufen: {cfg.loads_kg} (+ Baseline: {cfg.baseline_after_unload})")
    typer.echo(f"Runs: {cfg.runs}, erwartete Bilder: {total}")


@app.command("check-manifest")
def check_manifest_cmd(
    manifest: Path = Path("data/manifest.csv"),
    bars: Path = Path("config/bars.yaml"),
    analysis: Path = Path("config/analysis.yaml"),
) -> None:
    """Manifest auf Vollständigkeit, Duplikate und Unerwartetes prüfen."""
    problems = check_manifest(pd.read_csv(manifest), load_bars(bars), load_analysis(analysis))
    for p in problems:
        typer.echo(p)
    if problems:
        raise typer.Exit(code=1)
    typer.echo("Manifest vollständig und konsistent.")
