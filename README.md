# Barbellscan

Bildbasierte Auswertung der Durchbiegung von Powerlifting-Langhanteln: Marker-Tracking (OpenCV), Kalibrierung, Validierung und Statistik für die Seminararbeit
*Standardisation vs. Flexibility: A Quantitative Analysis of Barbell Deflection Under Heavy Loads Across Federation Regulations*.

- Anforderungen: [docs/PRD.md](docs/PRD.md)
- Zeitplan und Meilensteine: [docs/ROADMAP.md](docs/ROADMAP.md)

## Setup
```
uv sync
uv run pytest
uv run barbellscan --help
```

## Synthetische Daten und Tracking (M1)
```
uv run barbellscan simulate --out data/synthetic        # 700 Bilder, manifest.csv, truth.csv
uv run barbellscan track --manifest data/synthetic/manifest.csv --out data/derived/tracking.csv
uv run barbellscan compare --tracking data/derived/tracking.csv --truth data/synthetic/truth.csv
uv run barbellscan overlay <bild.jpg>                    # QC-Overlay mit erkannten Markern
```

## Daten
Rohbilder liegen **nicht** im Git (`data/raw/`, ignoriert). Im Repo liegen Manifest (`data/manifest.csv`) und abgeleitete Ergebnisse (`data/derived/`).
