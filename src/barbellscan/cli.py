"""Kommandozeile. Weitere Befehle (simulate, track, ...) folgen in M1-M7."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

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


@app.command()
def simulate(
    out: Path = Path("data/synthetic"),
    bars: Path = Path("config/bars.yaml"),
    analysis: Path = Path("config/analysis.yaml"),
    scale: float = typer.Option(1.0, help="Bildmaßstab in px/mm"),
    seed: int | None = typer.Option(None, help="Überschreibt den Seed aus der Config"),
    only: Annotated[
        list[str] | None, typer.Option(help="Nur diese bar_ids erzeugen (mehrfach angebbar)")
    ] = None,
    jobs: int = -1,
) -> None:
    """Synthetischen Datensatz (Bilder, manifest.csv, truth.csv) erzeugen."""
    from .simulate import SimParams, generate_dataset

    truth = generate_dataset(
        out,
        load_bars(bars),
        load_analysis(analysis),
        SimParams(scale_px_per_mm=scale),
        seed=seed,
        only_bars=only or None,
        n_jobs=jobs,
    )
    typer.echo(f"{len(truth)} Bilder nach {out} geschrieben.")


@app.command()
def track(
    manifest: Path = Path("data/synthetic/manifest.csv"),
    out: Path = Path("data/derived/tracking.csv"),
    jobs: int = -1,
) -> None:
    """Marker detektieren und D1 für alle Bilder des Manifests berechnen."""
    from .tracking import track_manifest

    df = track_manifest(manifest, n_jobs=jobs)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    flagged = int((df["quality_flags"].fillna("") != "").sum())
    typer.echo(f"{len(df)} Bilder ausgewertet, {flagged} mit Flags -> {out}")


@app.command()
def compare(
    tracking: Path = Path("data/derived/tracking.csv"),
    truth: Path = Path("data/synthetic/truth.csv"),
) -> None:
    """Tracking-Ergebnis gegen synthetische Ground Truth vergleichen (Bias, RMSE, LoA)."""
    from .validation import compare_to_truth

    for k, v in compare_to_truth(pd.read_csv(tracking), pd.read_csv(truth)).items():
        typer.echo(f"{k}: {v:.4f}" if isinstance(v, float) else f"{k}: {v}")


@app.command()
def overlay(
    image: Path,
    out: Path = Path("outputs/overlay.png"),
) -> None:
    """Einzelbild auswerten und QC-Overlay speichern."""
    import cv2

    from .tracking import draw_overlay, track_image

    img = cv2.imread(str(image), cv2.IMREAD_COLOR)
    row = track_image(img)
    out.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out), draw_overlay(img, row))
    typer.echo(f"D1 = {row['d1_mm']:.3f} mm, Flags: {row['quality_flags'] or '-'}")
