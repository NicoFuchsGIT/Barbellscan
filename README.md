# Barbellscan

Bildbasierte Auswertung der Durchbiegung von Powerlifting-Langhanteln: Marker-Tracking (OpenCV), Skalierung, Validierung und Statistik.

- **Analyseplan (verbindlich):** [docs/ANALYSIS_PLAN.md](docs/ANALYSIS_PLAN.md)
- Anforderungen: [docs/PRD.md](docs/PRD.md) · Zeitplan: [docs/ROADMAP.md](docs/ROADMAP.md)

## Setup
```
uv sync
uv run pytest
uv run barbellscan --help
```

## Echte Fotos auswerten
Die 663 JPEGs liegen nicht im Git. Entweder nach `data/raw/` kopieren oder mit `--image-root` auf den Ordner zeigen.

```
uv run barbellscan check-manifest --verify --image-root "C:\Users\nico2\Desktop\Bilder\umbenannt"
uv run barbellscan track --image-root "C:\Users\nico2\Desktop\Bilder\umbenannt" --overlay-dir outputs/overlays
uv run barbellscan deflect
```

| Befehl | Ergebnis |
|---|---|
| `check-manifest --verify` | Vollständigkeit (13 × 3 × 17) und SHA-256 jeder Bilddatei |
| `track` | `data/derived/tracking.csv`: Markerpositionen (px; Bänder als Punkt auf der Schaftachse, robust gegen herabhängende Bandenden), Kugel-/Ringabstand, `d1_px`, `dring_px`, Detektions-Flags (u. a. `tape_hanging_*`, `missing_*`); mit `--overlay-dir` ein QC-Bild je Foto |
| `deflect` | `data/derived/deflection.csv` (Skala je Zyklus, D1, ΔD1, ΔD_ring in mm), `cycle_summary.csv` (Nachgiebigkeit, ΔD1 bei 405 kg, Restverformung, Hysterese je Zyklus), `bar_summary.csv` (je Stange) |
| `overlay <bild> --bar <bar_id>` | QC-Bild für ein einzelnes Foto (zum Justieren von ROI/Schwellen in `config/analysis.yaml`) |

Pilot zuerst mit einem Foto pro Stange, z. B.:
```
uv run barbellscan overlay "C:\Users\nico2\Desktop\Bilder\umbenannt\Eleiko2016CompA0164.JPG" --bar eleiko_comp_2016
```

Das Manifest `data/manifest.csv` wurde aus der QC-Datei erzeugt (`barbellscan import-qc manifest_qc.csv`).

## Synthetische Daten (Validierung V1)
```
uv run barbellscan simulate --out data/synthetic
uv run barbellscan track --manifest data/synthetic/manifest.csv --analysis data/synthetic/analysis.yaml --out data/synthetic/tracking.csv
uv run barbellscan deflect --tracking data/synthetic/tracking.csv --analysis data/synthetic/analysis.yaml --out data/synthetic/deflection.csv --cycles-out data/synthetic/cycles.csv --bars-out data/synthetic/bars.csv
uv run barbellscan compare --deflection data/synthetic/deflection.csv --truth data/synthetic/truth.csv
```

## Daten
Rohbilder liegen **nicht** im Git (`data/raw/`, ignoriert). Im Repo liegen das Manifest mit SHA-256 (`data/manifest.csv`) und abgeleitete Ergebnisse (`data/derived/`).
