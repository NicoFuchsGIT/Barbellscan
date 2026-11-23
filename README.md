# Barbellscan

Bildbasierte Auswertung der Durchbiegung von Powerlifting-Langhanteln: Marker-Tracking (OpenCV), Skalierung, Validierung und Statistik.

- **Analyseplan (verbindlich):** [docs/ANALYSIS_PLAN.md](docs/ANALYSIS_PLAN.md)
- Anforderungen: [docs/PRD.md](docs/PRD.md) · Zeitplan: [docs/ROADMAP.md](docs/ROADMAP.md)

## Setup
Mit [uv](https://docs.astral.sh/uv/):
```
uv sync
uv run pytest
uv run barbellscan --help
```
Ohne uv (z. B. im PyCharm-Terminal), Python ≥ 3.13 in einer virtuellen Umgebung:
```
pip install -e .
barbellscan --help
```
In diesem Fall fällt in den Befehlen unten das `uv run` weg.

## Echte Fotos auswerten
Die 663 JPEGs liegen nicht im Git. Entweder nach `data/raw/` kopieren oder mit `--image-root` auf den Ordner zeigen.

```
uv run barbellscan check-manifest --verify --image-root "C:\Users\nico2\Desktop\Bilder\umbenannt"
uv run barbellscan track --image-root "C:\Users\nico2\Desktop\Bilder\umbenannt" --overlay-dir outputs/overlays
uv run barbellscan deflect
uv run barbellscan stats
uv run barbellscan plot
```

| Befehl | Ergebnis |
|---|---|
| `check-manifest --verify` | Vollständigkeit (13 × 3 × 17) und SHA-256 jeder Bilddatei |
| `track` | `data/derived/tracking.csv`: Markerpositionen (px; Bänder als Schwerpunkt in der Schaftzone, herabhängende Bandenden zählen nicht mit), Kugel-/Ringabstand, `d1_px`, `dring_px`, Detektions-Flags (u. a. `tape_hanging_*`, `missing_*`); mit `--overlay-dir` ein QC-Bild je Foto |
| `deflect` | `data/derived/deflection.csv` (Skala je Zyklus, D1, ΔD1, ΔD_ring in mm), `cycle_summary.csv` (Nachgiebigkeit, ΔD1 bei 405 kg, Restverformung, Hysterese je Zyklus), `bar_summary.csv` (je Stange) |
| `stats` | `data/derived/stats/`: `h1.csv` (exakter Permutationstest Deadlift vs. Power), `bars.csv` (Kenngrößen je Stange mit 95-%-KI), `categories.csv`, `pairs.csv` (Welch-Differenzen innerhalb eines Typs), `reliability.csv` (ICC(1,1), SEM, MDC95), `h2.csv` (Linearität, Restverformung, Hysterese gegen MDC95) |
| `plot` | `data/plots/`: `load_deflection_grid.png` (ΔD1 gegen Zusatzmasse je Stange, Be- und Entlastung), `load_deflection_overview.png` (alle Stangen in einem Bild), `dring_vs_moment_grid.png` (ΔD_ring gegen Lastmoment), `compliance_by_bar.png` (Nachgiebigkeit mit 95-%-KI), `h1_groups.png`, `h2_elasticity.png` (Linearität, Restverformung, Hysterese gegen MDC95); `--fmt pdf --fmt png` für weitere Formate |
| `overlay <bild> --bar <bar_id>` | QC-Bild für ein einzelnes Foto (zum Justieren von ROI/Schwellen in `config/analysis.yaml`) |

Bilder mit dokumentiertem Detektionsfehler (im Overlay nachvollziehbar) kommen mit Begründung in `data/exclusions.csv` (`image,reason`); `deflect` behandelt sie als fehlenden Wert. Sensitivitätsanalyse ohne unscharfe Bilder:
```
uv run barbellscan deflect --drop-qc-flag blur --out data/derived/sens_noblur/deflection.csv --cycles-out data/derived/sens_noblur/cycle_summary.csv --bars-out data/derived/sens_noblur/bar_summary.csv
```

Einzelnes Foto prüfen, z. B. nach einem Flag in `tracking.csv`:
```
uv run barbellscan overlay "C:\Users\nico2\Desktop\Bilder\umbenannt\Eleiko2016CompA0164.JPG" --bar eleiko_comp_2016
```

Das Manifest `data/manifest.csv` wurde einmalig aus der QC-Datei erzeugt (`barbellscan import-qc manifest_qc.csv`).

## Synthetische Daten (Validierung V1)
```
uv run barbellscan simulate --out data/synthetic
uv run barbellscan track --manifest data/synthetic/manifest.csv --analysis data/synthetic/analysis.yaml --out data/synthetic/tracking.csv
uv run barbellscan deflect --tracking data/synthetic/tracking.csv --analysis data/synthetic/analysis.yaml --out data/synthetic/deflection.csv --cycles-out data/synthetic/cycles.csv --bars-out data/synthetic/bars.csv
uv run barbellscan compare --deflection data/synthetic/deflection.csv --truth data/synthetic/truth.csv
```

## Daten
Rohbilder liegen **nicht** im Git (`data/raw/`, ignoriert). Im Repo liegen das Manifest mit SHA-256 (`data/manifest.csv`), die Ausschlussliste (`data/exclusions.csv`), die abgeleiteten Ergebnisse (`data/derived/`) und die Abbildungen (`data/plots/`). Nach einer Änderung an Code, Config oder Ausschlussliste `track` (nur bei Detektionsänderungen), `deflect`, `stats` und `plot` neu laufen lassen und die Ergebnisse mitcommitten. Overlays (`outputs/`) bleiben lokal.

## Projektstruktur
| Modul | Aufgabe |
|---|---|
| `config.py` | pydantic-Modelle für `config/bars.yaml` und `config/analysis.yaml` |
| `manifest.py` | Manifest einlesen, prüfen (Vollständigkeit, SHA-256), Import der QC-Datei |
| `detection.py` | Gelbe Kugeln und Bänder finden, Messpunkte bestimmen, QC-Overlay |
| `tracking.py` | Detektion über alle Bilder (parallel), `tracking.csv` |
| `deflection.py` | Skala, D1, ΔD1, ΔD_ring, Lastmoment, Kenngrößen je Zyklus und Stange |
| `stats.py` | H1, H2, Deskriptiv, ICC/SEM/MDC95 (Analyseplan Abschnitt 6) |
| `plots.py` | Abbildungen nach `data/plots/` |
| `simulate.py`, `validation.py` | Synthetische Bilder mit Ground Truth und Vergleich (V1) |
| `cli.py` | Befehle (`barbellscan --help`) |
