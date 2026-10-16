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

## Daten
Rohbilder liegen **nicht** im Git (`data/raw/`, ignoriert). Im Repo liegen Manifest (`data/manifest.csv`) und abgeleitete Ergebnisse (`data/derived/`).
