# Roadmap – Barbellscan

Stand: 16.10.2026 (CW 42). Abgeleitet aus dem Zeitplan (Table 3) im Concept Draft und dem [PRD](PRD.md). Die Reihenfolge ist so gewählt, dass **keine Phase auf echte Fotos warten muss**, bis die Pipeline steht.

## Überblick

| Meilenstein | Zeitraum (CW) | Fixtermin im Studienplan | Ergebnis |
|---|---|---|---|
| **M0** Fundament | 42 | | Repo, Toolchain, CI, Config, Datenmodell |
| **M1** Synthetik + Kern-Tracking | 42–43 | **Zwischenpräsentation 1 (CW 43)** | Synthetische Bilder, Detektion (gelbe Kugeln, Tape, Hintergrund-ArUco), erste Durchbiegung D1 |
| **M2** Kalibrierung + Skalierung | 43–45 | | Undistortion, Homographie, px→mm, Reprojektionsfehler |
| **M3** Vollständige Messkette + QC | 44–46 | | D1–D4 mit Unsicherheit, Flags, QC-Bericht, Echtdaten-tauglich |
| **M4** Echtdaten einspielen | sobald Fotos vorliegen (Ziel ≤ 46) | | Manifest, erste echte Auswertung, Markerentscheidung |
| **M5** Validierung | 45–47 | | V1–V5 durchgeführt, Unsicherheitsbudget |
| **M6** Statistik | 46–48 | **Zwischenpräsentation 2 (CW 48)** | H1/H2-Analyse, Reliabilität, Statistik-Tabellen |
| **M7** Paper-Outputs | 49–51 | | Table 2, Kurven, Statistik-Tabellen finalisiert |
| **M8** Freeze und Abgabe | 52–4 | Upload CW 1, Review bis CW 3, Final CW 4 | Reproduktionslauf, Release-Tag, Doku |

> Hinweis: Der Plan sah das Fotoshooting in CW 40 vor, Bilder liegen laut Interview noch nicht vor. M4 ist deshalb der kritische Punkt. Verschiebt sich M4 über CW 46 hinaus, werden M5 (V2, V3, V5) und M6 komprimiert, M1–M3 und V1 bleiben unberührt.

```
CW   42 43 44 45 46 47 48 49 50 51 52 53  1  2  3  4
M0   ██
M1   ██ ██                                   ▲ Präsentation 1 (CW 43)
M2      ██ ██ ██
M3         ██ ██ ██
M4                  ░░ ░░  (abhängig von Fotos)
M5            ██ ██ ██
M6               ██ ██ ██                    ▲ Präsentation 2 (CW 48)
M7                        ██ ██ ██
M8                                 ██ ██ ██ ▲ Upload (CW 1) ▲ Final (CW 4)
```

---

## M0 – Fundament (CW 42) ✅ erledigt
- `uv init`, `pyproject.toml`, Python 3.14 prüfen (Wheels für OpenCV/SciPy), sonst Fallback als ADR.
- ruff, pytest, pre-commit, GitHub-Actions-CI (Lint + Tests).
- Ordnerstruktur laut PRD 10.2; `.gitignore` für `data/raw/`, `outputs/`.
- Pydantic-Config-Modelle; `config/bars.yaml` aus Table 1 (13 Modelle, Squat mit 2 Exemplaren, Eigengewichte).
- Tidy-Datenmodell und Manifest-Schema (FR-01–03).

**Fertig, wenn:** `uv run pytest` und CI sind grün, `barbellscan --help` läuft, `bars.yaml` validiert.

## M1 – Synthetik und Kern-Tracking (CW 42–43) ✅ erledigt
- Generator für synthetische Bilder (FR-15): Biegelinie, gelbe Kugeln an den Enden, Tape-Mitte, ArUco im Hintergrund, Scheiben und Klemmen, Rauschen, Kamerarolle.
- Detektion: ArUco-Referenz (FR-06), gelbe Kugeln über die Farbe (FR-07), Tape (FR-08), jeweils mit Subpixel-Schwerpunkt.
- D1 aus drei Punkten, Ausgabe als Tidy-CSV.
- **Demo für Zwischenpräsentation 1:** synthetisches Bild → erkannte Marker → Durchbiegung → Soll/Ist-Vergleich, plus kurze Vorstellung des Analyseplans.

**Fertig, wenn:** auf 100 synthetischen Bildern mit bekannter Biegung liegt der absolute Fehler unter dem vorläufigen Zielwert (0,5 mm) bei ungestörten Bedingungen.

**Ergebnis (700 synthetische Bilder mit Scheiben/Klemmen, gelbe Kugeln, Hintergrund-ArUco, 1 px/mm, 0,3° Kamerarolle, Rauschen, Unschärfe):** Detektionsrate 100 %, Bias +0,03 mm, SD 0,02 mm, 95-%-LoA −0,01 bis +0,07 mm, maximaler Fehler 0,10 mm. Der Bias stammt aus der Skala des Markers (−0,3 %). Das gilt nur für ungestörte Bedingungen ohne Linsenverzerrung und Perspektive und mit dem Marker in der Stangenebene. Diese Störgrößen kommen in M2/M5 (V1) dazu.

## M2 – Kalibrierung und Skalierung (CW 43–45)
- Intrinsische Kalibrierung mit Schachbrett/ChArUco, RMS-Reprojektionsfehler (FR-05).
- Skala über das Hintergrund-ArUco, Gegenprobe Referenzquadrat; Tiefenversatz der Markerebene als Unsicherheit (FR-09). Homographie/Perspektive.
- Synthetische Linsenverzerrung und Perspektive in V1 einbauen; Korrektur gegen Ground Truth testen.
- Linsenverzerrung im Simulator, Kalibrierung dagegen testen (ein einzelner zentraler Marker reicht dafür nicht).

**Fertig, wenn:** Skala- und Verzerrungsfehler auf Synthetik quantifiziert, Kalibrierprotokoll für das echte Setup liegt als Vorlage vor.

## M3 – Vollständige Messkette und QC (CW 44–46)
- D1–D4 mit Unsicherheit (FR-10, FR-11), Biegelinie per Spline mit geraden Sleeves.
- Qualitätsflags (FR-12), QC-Bericht mit Overlay (FR-13), `barbellscan run` End-to-End, Parallelisierung und Cache.
- Manifest-Prüfung auf Vollständigkeit (14 × 5 × 10 Bilder).

**Fertig, wenn:** ein kompletter synthetischer Datensatz in Echtgröße (700 Bilder) läuft in unter 10 min und liefert Tidy-Dataset + QC-Bericht.

## M4 – Echtdaten einspielen (Ziel spätestens CW 46)
- Fotos ablegen (lokal), Manifest mit SHA-256 erzeugen, Datenbackup.
- Erste Pilotauswertung (eine Stange, ein Run) → Detektionsparameter feinjustieren.
- Markergröße, Kugeldurchmesser und Marker-Tiefe (O8) sowie Kamera-/Kalibrierprotokoll (O5) dokumentieren und in die Config eintragen.
- Ergebnisdaten ins Git (`data/derived/`).

**Fertig, wenn:** ≥ 95 % der Bilder werden ohne manuellen Eingriff erkannt, geflaggte Bilder sind nachvollziehbar behandelt.

## M5 – Validierung (CW 45–47)
- V1: Sensitivitätsstudie auf Synthetik (Verzerrung, Winkel, Rauschen, Licht, Markerneigung) und Festlegung der Akzeptanzschwelle (O7).
- V2: Kalibrier- und Reprojektionsfehler, Skalenkonsistenz Referenzquadrat ↔ ArUco, Marker-Jitter.
- V3: Stichprobenhafte grafische Nachbildung/Gegencheck an zufälligen 5 % der Bilder.
- V4: Balkenmodell implementiert und mit gemessenen Daten verglichen.
- V5: Reliabilität (ICC, SEM, MDC95, CV).
- Unsicherheitsbudget als eigenes Kapitel/Tabelle für Methods.

**Fertig, wenn:** Validierungsbericht mit allen Kennzahlen liegt vor, die Messunsicherheit (95 %) ist bekannt und in den Datensatz übernommen.

## M6 – Statistik (CW 46–48)
- **Analyseplan einfrieren** (Git-Tag `analysis-plan-v1`) vor der Sichtung der Echtdaten-Ergebnisse.
- Deskriptiv (FR-20), Linearität (FR-21), Restverformung (FR-22), Kategorienvergleich (FR-23), Holm und Diagnostik (FR-24).
- Tests der Statistikfunktionen gegen Referenzwerte (R/SciPy-Beispiele, synthetische Daten mit bekannter Wahrheit).
- **Zwischenpräsentation 2 (CW 48):** erste echte Ergebnisse für H1/H2 mit Messunsicherheit.

**Fertig, wenn:** alle Tests laufen mit festem Seed reproduzierbar, Tabellen für H1/H2 liegen vor.

## M7 – Paper-Outputs (CW 49–51)
- Table 2 mit Farbverlauf (FR-26), Load-Deflection-Kurven mit SD-Band und Biegelinien (FR-27), Statistik-Tabellen als LaTeX/CSV (FR-28), einheitlicher Stil (FR-29).
- Abbildungen in Paper-Format (Spaltenbreite, Schriftgrößen, englische Labels).
- Methodik-Doku und README mit Anleitung zur Reproduktion.

**Fertig, wenn:** alle Abbildungen und Tabellen der Arbeit werden vollständig aus `barbellscan report` erzeugt.

## M8 – Freeze und Abgabe (CW 52–CW 4)
- Reproduktionslauf auf sauberem Checkout (`uv sync && barbellscan run`), Abgleich aller Zahlen im Manuskript.
- Release-Tag (`v1.0-seminar`), `CITATION.cff`, Daten-/Software-Availability-Statement.
- Review-Feedback (bis CW 3) einarbeiten, finale Version CW 4.

**Fertig, wenn:** Ergebnisse im Manuskript stimmen bytegenau mit den erzeugten Tabellen überein und das Repo ist getaggt.

---

## Abhängigkeiten und Entscheidungspunkte

| Entscheidung | Spätestens | Blockiert |
|---|---|---|
| O1 Primäre Durchbiegungsdefinition (Vorschlag D1) | Ende M2 | Analyseplan, M6 |
| O8 Markergröße/Tiefe, Kugeldurchmesser | vor Fotoshooting | Skala (FR-09) |
| O3 Baseline-Fotos (vor und nach Run) | vor Fotoshooting | H2 |
| O5 Kamera/Kalibrierprotokoll | vor Fotoshooting | M2 mit Echtdaten |
| O7 Akzeptanzschwelle | M5 | Validierungsurteil |

## Zeitpuffer und Priorisierung bei Engpass
1. **Unverzichtbar:** M1–M3, D1, V1/V2/V5, H1-Test, Linearität, Table 2, Kurven.
2. **Wichtig:** V3, V4, Restverformung (H2), QC-Bericht.
3. **Streichbar zuerst:** D2–D4-Vergleich, manueller Override, Mixed Models, DVC, Web-UI.

## Nächste Schritte (diese Woche)
1. M0 aufsetzen und committen.
2. Demo für CW 43 mit dem neuen Markerkonzept (gelbe Kugeln, Hintergrund-ArUco).
3. Offene Entscheidungen O1, O3, O5 mit den Betreuern klären, bevor fotografiert wird.
4. Concept Draft und Slides auf 425 kg / 9 Stufen / ohne RQ2/H3 angleichen.
