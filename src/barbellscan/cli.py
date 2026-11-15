"""Kommandozeile (ANALYSIS_PLAN v1.0)."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import pandas as pd
import typer

from . import __version__
from .config import load_analysis, load_bars
from .manifest import check_manifest, expected_design, from_qc_csv, verify_images

app = typer.Typer(help="Barbellscan: Durchbiegungsanalyse von Langhanteln", no_args_is_help=True)

BARS = typer.Option(Path("config/bars.yaml"), help="Stangen-Katalog")
ANALYSIS = typer.Option(Path("config/analysis.yaml"), help="Analyse-Config")
ImageRoot = Annotated[
    Path | None,
    typer.Option(help="Ordner mit den Bildern (statt Pfad relativ zum Manifest)"),
]


@app.command()
def version() -> None:
    """Version ausgeben."""
    typer.echo(__version__)


@app.command()
def design(bars: Path = BARS, analysis: Path = ANALYSIS) -> None:
    """Studiendesign aus der Config zusammenfassen."""
    catalog, cfg = load_bars(bars), load_analysis(analysis)
    cats = pd.Series([b.category for b in catalog.bars]).value_counts()
    typer.echo(f"Stangen: {len(catalog.bars)} ({', '.join(f'{k} {v}' for k, v in cats.items())})")
    typer.echo(f"Zyklen: {', '.join(cfg.cycles)}; Stufen je Zyklus: {len(cfg.schedule())}")
    typer.echo("Zusatzmasse: " + ", ".join(f"{s.added_mass_kg:g}" for s in cfg.schedule()) + " kg")
    typer.echo(f"Erwartete Bilder: {len(expected_design(catalog, cfg))}")


@app.command("import-qc")
def import_qc(
    qc_csv: Path,
    out: Path = Path("data/manifest.csv"),
    image_dir: str = typer.Option("raw", help="Bildordner relativ zum Manifest"),
    bars: Path = BARS,
    analysis: Path = ANALYSIS,
) -> None:
    """manifest_qc.csv (QC-Export) in das Manifest-Schema übersetzen."""
    m = from_qc_csv(pd.read_csv(qc_csv), load_bars(bars), load_analysis(analysis), image_dir)
    out.parent.mkdir(parents=True, exist_ok=True)
    m.to_csv(out, index=False)
    typer.echo(f"{len(m)} Zeilen -> {out}")


@app.command("check-manifest")
def check_manifest_cmd(
    manifest: Path = Path("data/manifest.csv"),
    bars: Path = BARS,
    analysis: Path = ANALYSIS,
    verify: bool = typer.Option(False, help="Bilddateien und SHA-256 prüfen"),
    image_root: ImageRoot = None,
) -> None:
    """Manifest auf Vollständigkeit, Duplikate und Konsistenz prüfen (optional SHA-256)."""
    m = pd.read_csv(manifest, dtype={"cycle": str})
    problems = check_manifest(m, load_bars(bars), load_analysis(analysis))
    if verify:
        problems += verify_images(m, manifest.parent, image_root)
    for p in problems:
        typer.echo(p)
    if problems:
        raise typer.Exit(code=1)
    typer.echo(f"Manifest vollständig und konsistent ({len(m)} Bilder).")


@app.command()
def simulate(
    out: Path = Path("data/synthetic"),
    bars: Path = BARS,
    analysis: Path = ANALYSIS,
    scale: float = typer.Option(1.0, help="Bildmaßstab in px/mm"),
    seed: int | None = typer.Option(None, help="Überschreibt den Seed aus der Config"),
    only: Annotated[
        list[str] | None, typer.Option(help="Nur diese bar_ids erzeugen (mehrfach angebbar)")
    ] = None,
    jobs: int = -1,
) -> None:
    """Synthetischen Datensatz (Bilder, manifest.csv, truth.csv, analysis.yaml) erzeugen."""
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
    typer.echo(f"{len(truth)} Bilder nach {out} geschrieben (Config: {out / 'analysis.yaml'}).")


@app.command()
def track(
    manifest: Path = Path("data/manifest.csv"),
    out: Path = Path("data/derived/tracking.csv"),
    bars: Path = BARS,
    analysis: Path = ANALYSIS,
    image_root: ImageRoot = None,
    overlay_dir: Annotated[
        Path | None, typer.Option(help="QC-Overlay je Bild hierhin schreiben")
    ] = None,
    full_frame: bool = typer.Option(False, help="ROI ignorieren"),
    jobs: int = -1,
) -> None:
    """Marker in allen Bildern des Manifests detektieren (Ergebnis in Pixeln)."""
    from .tracking import track_manifest

    df = track_manifest(
        manifest,
        load_bars(bars),
        load_analysis(analysis),
        n_jobs=jobs,
        full_frame=full_frame,
        image_root=image_root,
        overlay_dir=overlay_dir,
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    flagged = df[df["detect_flags"].fillna("") != ""]
    typer.echo(f"{len(df)} Bilder ausgewertet, {len(flagged)} mit Detektions-Flags -> {out}")
    for flag, n in flagged["detect_flags"].str.split(";").explode().value_counts().items():
        typer.echo(f"  {flag}: {n}")


@app.command()
def deflect(
    tracking: Path = Path("data/derived/tracking.csv"),
    out: Path = Path("data/derived/deflection.csv"),
    cycles_out: Path = Path("data/derived/cycle_summary.csv"),
    bars_out: Path = Path("data/derived/bar_summary.csv"),
    bars: Path = BARS,
    analysis: Path = ANALYSIS,
) -> None:
    """Skala (Ringbänder), D1/ΔD1, D_ring/ΔD_ring und Kenngrößen je Zyklus und Stange."""
    from .deflection import add_deflection, bar_summary, cycle_summary

    catalog, cfg = load_bars(bars), load_analysis(analysis)
    df = add_deflection(pd.read_csv(tracking, dtype={"cycle": str}), catalog, cfg)
    cyc = cycle_summary(df, cfg)
    per_bar = bar_summary(cyc, catalog)
    for path, frame in ((out, df), (cycles_out, cyc), (bars_out, per_bar)):
        path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(path, index=False)
    n_valid = int(df["delta_d1_mm"].notna().sum())
    typer.echo(f"ΔD1 für {n_valid}/{len(df)} Bilder -> {out}")
    typer.echo(f"Zyklen -> {cycles_out}, Stangen -> {bars_out}")


@app.command()
def compare(
    deflection: Path = Path("data/derived/deflection.csv"),
    truth: Path = Path("data/synthetic/truth.csv"),
) -> None:
    """Auswertung gegen synthetische Ground Truth vergleichen (Bias, RMSE, LoA)."""
    from .validation import compare_to_truth

    stats = compare_to_truth(pd.read_csv(deflection), pd.read_csv(truth))
    for k, v in stats.items():
        typer.echo(f"{k}: {v:.4f}" if isinstance(v, float) else f"{k}: {v}")


@app.command()
def overlay(
    image: Path,
    bar_id: str = typer.Option(..., "--bar", help="bar_id aus config/bars.yaml"),
    out: Path = Path("outputs/overlay.jpg"),
    bars: Path = BARS,
    analysis: Path = ANALYSIS,
    full_frame: bool = typer.Option(False, help="ROI ignorieren"),
) -> None:
    """Einzelbild auswerten und QC-Overlay speichern."""
    import cv2

    from .tracking import draw_overlay, track_image

    cfg = load_analysis(analysis)
    img = cv2.imread(str(image), cv2.IMREAD_COLOR)
    if img is None:
        raise typer.BadParameter(f"Bild nicht lesbar: {image}")
    row = track_image(img, load_bars(bars).bar(bar_id), cfg, full_frame)
    roi = None if full_frame else cfg.detection.roi_frac
    out.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out), draw_overlay(img, row, roi, title=image.name))
    typer.echo(
        f"d1 = {row['d1_px']:.2f} px, Ringabstand = {row['ring_dist_px']:.1f} px, "
        f"Flags: {row['detect_flags'] or '-'} -> {out}"
    )
