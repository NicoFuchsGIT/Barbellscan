# PRD – Barbellscan: Datenauswertung, Validierung und Statistik

| | |
|---|---|
| **Projekt** | *Standardisation vs. Flexibility: A Quantitative Analysis of Barbell Deflection Under Heavy Loads Across Federation Regulations* (Human Factors and Sports Engineering, Wien) |
| **Autor** | Nico Fuchs |
| **Betreuer** | MSc. Markus Eckelt, MSc. Alexander Renner |
| **Status** | v0.2 (16.10.2026, CW 42): Interview-Ergebnis, Markerkonzept aktualisiert. M0 und M1 umgesetzt (siehe [ROADMAP](ROADMAP.md)). **Seit 15.11.2026 gilt bei Widersprüchen der [Analyseplan](ANALYSIS_PLAN.md) (Design, Marker, Zielgrößen, Statistik).** |
| **Quellen** | Concept Draft (.docx), Draft-Präsentation (.pptx), Creo-Modell Sleeve-Aufsatz (`kk.prt`) |

---

## 1. Kontext und Ziel

Powerlifting-Verbände schreiben unterschiedliche Stangentypen vor (Power-, Squat-, Deadlift-Bar). Deren Geometrie und Material bestimmen die elastische Durchbiegung („Whip“), die Athleten spüren, aber bisher nicht objektiv vergleichbar ist. Das Seminarprojekt misst die Durchbiegung von 13 Stangenmodellen bildbasiert (Marker an Mitte und Sleeve-Enden, Monolift, stufenweise Beladung).

**Dieses Repo liefert die gesamte Datenauswertung**: von den Rohfotos über Marker-Tracking und Kalibrierung bis zu Durchbiegungswerten, Validierung der Messmethode, Statistik und fertigen Tabellen/Abbildungen für die Seminararbeit. Hardware-Aufbau, Fotoshooting und das Schreiben der Arbeit sind nicht Teil des Repos.

### Produktziel in einem Satz
Ein reproduzierbarer Befehl (`barbellscan run`) verwandelt Fotos und Metadaten in belastbare Durchbiegungswerte mit Messunsicherheit, getesteten Hypothesen und paper-fertigen Outputs.

### Erfolgskriterien
1. Alle Zahlen, Tabellen und Abbildungen der Arbeit lassen sich aus Rohdaten + Config per Befehl exakt neu erzeugen (gleicher Git-Commit ⇒ gleiche Ergebnisse).
2. Die Messunsicherheit des Tracking-Systems ist quantifiziert und in jedem Ergebnis mitgeführt.
3. H1 und H2 sind mit vorab festgelegtem Analyseplan (Abschnitt 8) ausgewertet und berichtet.
4. Die Pipeline ist bereits vor dem Fotoshooting auf synthetischen Daten vollständig getestet.

---

## 2. Entscheidungen aus dem Interview

| Thema | Entscheidung |
|---|---|
| Umfang | Komplette Pipeline (Bilder → Tracking → Kalibrierung → Durchbiegung → Statistik → Plots/Tabellen) |
| Datenstand | **Noch keine Bilder.** Entwicklung zuerst gegen synthetische Daten |
| Forschungsfragen | **Nur RQ1.** RQ2/H3 (Validität des optischen Systems als Sensor-Alternative) wurden offiziell entfernt (siehe .docx) |
| Validierung | Trotzdem Pflicht als Qualitätsnachweis in Methods/Discussion, aber ohne eigene Hypothese: (a) sporadische grafische Nachbildung der Biegung, (b) Kalibrier-/Reprojektionsfehler, (c) Balkenmodell als Plausibilitätscheck. Zusätzlich empfohlen: synthetische Ground Truth und Run-Reliabilität (siehe 7) |
| Durchbiegungsdefinition | Offen: Pipeline berechnet mehrere Definitionen parallel (siehe 5.3) |
| Laststufen | **20, 75, 125, …, 425 kg** (9 Stufen, 50-kg-Schritte). Maximallast von 525 auf 425 kg reduziert, da 525 kg bei den Deadlift-Bars als riskant eingestuft wurde |
| Durchgänge | 5 Runs aufsteigend, danach Entlastung auf 20 kg bzw. leere Stange als **Baseline-Foto** (Restverformung für H2) |
| Statistik | Solide Standard-Inferenz, Hantel als Analyseeinheit, Kategorienvergleich Power vs. Deadlift inferenziell, Squat deskriptiv |
| Squat-Bars | 2 physische Squat-Bars, gleicher Hersteller und gleiches Modell (Texas) |
| Output | Paper-fertige Plots und Tabellen (matplotlib + SciencePlots), Rohdaten als Tidy-Dataset |
| Tech | uv, pytest, ruff, Python 3.14 (wie im Draft) |
| Doku-Sprache | Dokumentation Deutsch, Plot-Beschriftungen und Paper-Outputs Englisch |

---

## 3. Nutzer und Nutzungsszenarien

**Primärer Nutzer:** Nico (Analyst, schreibt die Arbeit). **Sekundär:** Betreuer (Reproduzierbarkeit, Nachvollziehen der Methodik), spätere Studierende, die das Verfahren wiederverwenden.

| Szenario | Ablauf |
|---|---|
| S1 Entwicklung ohne Daten | `barbellscan simulate` erzeugt synthetische Bilder mit bekannter Biegung; Pipeline läuft, Validierungsfehler werden gemessen |
| S2 Kalibrierung | Kamera-Intrinsics aus Schachbrett-/ChArUco-Bildern, Reprojektionsfehler dokumentiert |
| S3 Auswertung nach Shooting | Fotos + Manifest ablegen, `barbellscan run`, QC-Bericht prüfen, Problemfälle gezielt nachbearbeiten |
| S4 Paper | `barbellscan report` erzeugt Table 2, Load-Deflection-Kurven, Statistik-Tabellen, alles englisch beschriftet |

---

## 4. Forschungsfrage und Hypothesen (Stand: nach Streichung RQ2/H3)

- **RQ1:** Wie unterscheidet sich die maximale vertikale Durchbiegung zwischen verbandsspezifischen Stangen über das Lastspektrum bis **425 kg**?
- **H1:** Die Deadlift-Bar zeigt signifikant größere Durchbiegung als Power- und Squat-Bars (Begründung: Ø 27 mm, größere Länge).
- **H2:** Alle Stangen verhalten sich bis zur Maximallast linear-elastisch und kehren ohne plastische Verformung zur Baseline zurück.

> Die Präsentation (21.09.) nennt noch RQ2/H3, das .docx nicht mehr. Die Slides sollten angepasst werden, damit beide Dokumente übereinstimmen.

---

## 5. Studiendesign und Datenmodell

### 5.1 Design
- 13 Stangenmodelle (9 Power, 3 Deadlift, 1 Squat-Modell), davon Squat in **2 physischen Exemplaren** ⇒ **14 physische Stangen**.
- 9 Laststufen × 5 Runs. Pro Run zusätzlich 1 Baseline-Foto nach Entlastung.
- Erwartete Bildmenge: 14 × 5 × (9 + 1) = **700 Bilder** (Draft nennt 715 für 11 Stufen, nicht mehr gültig).
- Aufbau: Legend Monolift, Auflagepunkte ca. ±371 mm vom Zentrum (J-Hooks), Marker (Stand 16.10.2026): **gelbe Kugel** an jeder Sleeve-Kappe (Stangenenden), **Elektroband** in der Stangenmitte, **ein ArUco-Referenzmarker im Hintergrund** (Bildmitte) nur für Pixel→mm und Kamera-Verzerrung. Der Slipring-Aufsatz mit ArUco an den Enden entfällt.

### 5.2 Tidy-Datenmodell (Single Source of Truth)
Eine Zeile pro Bild/Marker-Auswertung:

`bar_id, model_id, category, replicate (physische Stange), run, load_kg, is_baseline, image_path, image_sha256, marker_type, centre_xy, left_xy, right_xy, scale_mm_per_px, quality_flags, deflection_D1..Dn (mm), u_deflection (mm)`

Stangenstammdaten (Table 1: Länge, Ø, Zugfestigkeit, Schaftlänge, Hersteller, Artikelnr.) liegen versioniert in `config/bars.yaml`.

### 5.3 Durchbiegungsdefinitionen (alle werden berechnet)
Vorzeichenkonvention: Bei Beladung an den Sleeves und Auflage innen (Hooks) wölbt sich der Schaft zwischen den Hooks nach oben, die Enden hängen relativ dazu herab. Das Vorzeichen ist konfigurierbar, positiv = Enden unter Mitte.

| ID | Definition | Eigenschaft |
|---|---|---|
| **D1 (Primär, Vorschlag)** | Vertikaler Abstand der Mitte zur Sehne der beiden Endmarker | Robust gegen Kippen/Verschiebung der Kamera und der ganzen Stange |
| D2 | Mitte relativ zur Auflagelinie (±371 mm Hooks) | Setzt bekannte Auflage voraus, näher am Balkenmodell |
| D3 | Alle Marker relativ zur 20-kg-Baseline desselben Runs (Δ) | Eliminiert Eigengewicht/Vorkrümmung, sensitiv für Re-Seating |
| D4 | Rekonstruierte Biegelinie (Spline, siehe FR-10) und Maximum der Abweichung zur Sehne | Für die Kurvenplots, nicht nur 3 Punkte |

**D1 ist als primäre Zielgröße vorgeschlagen und muss vor der ersten Auswertung der echten Daten festgeschrieben werden (siehe 8.1, offene Entscheidung O1).**

---

## 6. Funktionale Anforderungen

Priorität: **M** = Muss, **S** = Soll, **K** = Kann.

### 6.1 Daten und Konfiguration
| ID | Anforderung | Prio |
|---|---|---|
| FR-01 | Einlesen von Foto-Ordner + Manifest (CSV/YAML): Zuordnung Datei ↔ Stange, Run, Last, Baseline. Prüfung auf Vollständigkeit (14 × 5 × 10), Duplikate, fehlende Stufen | M |
| FR-02 | SHA-256 pro Bild im Manifest; Ergebnisse verweisen darauf (Beweiskette ohne Bilder im Git) | M |
| FR-03 | Alle Parameter (Marker-Typ, Referenzquadrat-Größe, Auflageabstand, Kamera-Intrinsics, Laststufen, Schwellen) in versionierten YAML-Dateien | M |
| FR-04 | EXIF-Auslesung (Kamera, Brennweite, Zeitstempel) ins Datenmodell | S |

### 6.2 Kalibrierung und Tracking
| ID | Anforderung | Prio |
|---|---|---|
| FR-05 | Intrinsische Kalibrierung (Schachbrett/ChArUco), Ausgabe von Kameramatrix, Verzerrungskoeffizienten und **RMS-Reprojektionsfehler**; Undistortion pro Bild | M |
| FR-06 | Detektion des ArUco-Referenzmarkers im Hintergrund (OpenCV, ID 0), Subpixel-Eckenverfeinerung; liefert Skala (px/mm) und Bildneigung | M |
| FR-07 | Detektion der gelben Kugeln an den Sleeve-Kappen über die Farbe (zwei größte Blobs, links/rechts nach x, Subpixel-Zentroid per Bildmomente ohne harten Schwellwert); konstante Hängelänge `ball_hang_mm` wird von D1 abgezogen | M |
| FR-08 | Detektion Mittenmarker (farbiges Elektroband, HSV-Segmentierung, Zentroid in Subpixel) | M |
| FR-09 | Skalierung px→mm über die Kantenlänge des Hintergrund-ArUco (Config `aruco_size_mm`), optional Referenzquadrat als Gegenprobe; Tiefenversatz zwischen Markerebene und Stangenebene wird als Skalenkorrektur bzw. Unsicherheit berücksichtigt; Perspektiv-Rektifizierung per Homographie | M |
| FR-10 | Rekonstruktion der Biegelinie aus Markerpunkten (Spline/Polynom mit Randbedingung „Sleeves bleiben gerade“) | S |
| FR-11 | Berechnung D1–D4 pro Bild, jeweils mit Unsicherheit (Fehlerfortpflanzung aus Subpixel-Streuung + Skalenfehler) | M |
| FR-12 | Automatische Qualitätsflags (Marker nicht gefunden, Unschärfe, Marker-Neigung, Skala außerhalb Toleranz, Ausreißer ggü. Run) | M |
| FR-13 | QC-Bericht (HTML/PDF): Bild mit Overlay der erkannten Marker und Biegelinie, Filter auf geflaggte Bilder | S |
| FR-14 | Manueller Override: Markerpositionen für einzelne Bilder nachträglich setzen, Eingriff wird im Datensatz markiert | K |
| FR-31 | **Plattenzähler (Vorschlag, noch nicht bestätigt):** Scheibenzahl je Seite aus der Stapelbreite (mm über ArUco-Skala ÷ Scheibendicke) und den Trennkanten bestimmen; Abgleich mit dem Manifest (Last = 25 + 50·n kg), getrennt links/rechts. Flags bei falscher Zuordnung und asymmetrischer Beladung | S |
| FR-32 | ID-Tafel mit ArUco-Code (Stange, Run, Stufe) im Bild als deterministische Zuordnung (Vorschlag, optional) | K |

### 6.3 Validierung (Details in Abschnitt 7)
| ID | Anforderung | Prio |
|---|---|---|
| FR-15 | Generator für synthetische Bilder (bekannte Biegung, gelbe Kugeln, Hintergrund-ArUco, Scheiben und Klemmen passend zur Last, Kamerarolle, Rauschen; geplant: Linsenverzerrung, Perspektive, Beleuchtung, Kugelreflexe). Ladeprotokoll: 20 kg = leere Stange, sonst Last = 25 + 50·n kg mit n 25-kg-Scheiben je Seite inkl. Klemmen | M |
| FR-16 | Validierungsbericht: Bias, Streuung, Unsicherheit gegen Ground Truth | M |
| FR-17 | Stichprobenhafte grafische Nachbildung: Overlay der rekonstruierten Biegung auf dem Originalfoto + manueller Gegencheck an zufälliger, stratifizierter Stichprobe | M |
| FR-18 | Balkenmodell (Euler-Bernoulli, Überhangträger) mit Plausibilitätsvergleich zu gemessenen Werten | S |
| FR-19 | Reliabilität über 5 Runs (ICC, SEM, MDC95, CV) | M |

### 6.4 Statistik (Details in Abschnitt 8)
| ID | Anforderung | Prio |
|---|---|---|
| FR-20 | Deskriptive Statistik je Stange/Last/Kategorie (Mittelwert, SD, Min/Max, n) | M |
| FR-21 | Linearitätsanalyse je Stange und Run (OLS Last→Durchbiegung, R², Steifigkeit mm/100 kg mit CI, Test auf quadratischen Term) | M |
| FR-22 | Restverformungsanalyse (Baseline nach Entlastung vs. Baseline vor Belastung) mit Bezug auf MDC | M |
| FR-23 | Kategorievergleich (Power vs. Deadlift) mit Effektstärke und Bootstrap-CI; Squat deskriptiv | M |
| FR-24 | Mehrfachtest-Korrektur (Holm), Annahmen-Diagnostik, alle Tests mit Versionsstand und Seed reproduzierbar | M |

### 6.5 Output
| ID | Anforderung | Prio |
|---|---|---|
| FR-25 | Tidy-Dataset als CSV + Parquet | M |
| FR-26 | **Table 2**: Durchbiegung je Stange × Laststufe mit Farbverlauf, Zeilen für Ø Power/Deadlift/Squat | M |
| FR-27 | **Load-Deflection-Kurven** je Kategorie mit SD-Band und Biegelinien entlang der Stangenlänge (Figure 5 des Drafts als Vorlage, echte Daten statt AI-Skizze) | M |
| FR-28 | Statistik-Tabellen (H1, H2, Reliabilität, Kalibrierfehler) als LaTeX/CSV/Excel-kompatibel | M |
| FR-29 | Einheitlicher Plot-Stil (SciencePlots), Export PDF/SVG/PNG, englische Beschriftungen, farbenblindheitsfreundliche Palette | M |
| FR-30 | CLI: `simulate`, `calibrate`, `track`, `validate`, `analyze`, `report`, `run` (alles) | M |

---

## 7. Validierungsmethodik

Ziel: Nachweis, dass Messfehler klein gegenüber den gesuchten Effekten sind und bekannt ist, wie groß er ist. Keine eigene Hypothese, aber Pflichtkapitel in Methods/Discussion.

| # | Methode | Beschreibung | Kennzahlen | Verfügbar |
|---|---|---|---|---|
| V1 | **Synthetische Ground Truth** (empfohlen) | Gerenderte Bilder mit exakt bekannter Durchbiegung; Variation von Verzerrung, Perspektivwinkel, Auflösung, Rauschen, Licht, Markerneigung | Bias, RMSE, 95 %-Limits of Agreement, Sensitivitätsstudie je Störgröße | sofort |
| V2 | **Kalibrier-/Reprojektionsfehler** | Intrinsics aus Kalibrierbildern; Konsistenz Referenzquadrat ↔ ArUco-Skala; Subpixel-Streuung bei statischen Wiederholaufnahmen | RMS-Reprojektionsfehler (px), Skalenabweichung (%), Marker-Jitter (px → mm) | nach Kalibrieraufnahmen |
| V3 | **Sporadische grafische Nachbildung** | Rekonstruierte Biegelinie auf Originalfoto zeichnen; an einer zufälligen, nach Stange/Last stratifizierten Stichprobe (Vorschlag 5 %) werden Markerpositionen von Hand gesetzt und mit der automatischen Detektion verglichen | Pixel-/mm-Differenz, Anteil Abweichungen > Toleranz | nach Shooting |
| V4 | **Balkenmodell-Plausibilität** | Überhangträger auf zwei Auflagern (±371 mm), Schaft mit I = πd⁴/64, E ≈ 200–210 GPa, Sleeves als starr. **Zugfestigkeit ist kein Steifigkeitsmaß** und geht nicht in die Durchbiegung ein; Abweichung ⇒ Hinweis auf Geometrie, Sleeve-Steifigkeit, Auflage | Verhältnis gemessen/modelliert je Stange und Last, Abhängigkeit von d⁴ | sofort (Modell), nach Shooting (Vergleich) |
| V5 | **Run-Reliabilität** (empfohlen) | 5 Wiederholungen je Stange und Last; schließt Re-Seating und Bildaufnahme ein | ICC(2,1), SEM, MDC95, CV | nach Shooting |

**Akzeptanzvorschlag (zu bestätigen nach V1):** erweiterte Messunsicherheit (95 %) der Durchbiegung ≤ 0,5 mm und ≤ 10 % des kleinsten erwarteten Unterschieds zwischen Kategorien bei 425 kg. Der Schwellenwert wird erst festgelegt, wenn V1 realistische Werte für die Auflösung der verwendeten Kamera zeigt.

---

## 8. Statistischer Analyseplan

### 8.1 Grundsätze
- **Analyseeinheit ist die physische Stange.** Die 5 Runs sind Wiederholmessungen; je Stange und Last wird der Run-Mittelwert verwendet, die Run-Streuung geht in die Reliabilität ein. Pseudoreplikation wird vermieden.
- **Primäre Zielgröße:** D1 bei 425 kg (Vorschlag). Weitere Laststufen und Definitionen D2–D4 sind Sensitivitätsanalysen.
- Signifikanzniveau α = 0,05, Holm-Korrektur für Familien von Tests, alle Ergebnisse mit 95 %-KI und Effektstärke.
- Wegen kleiner n (3 Deadlift-Bars) **robuste/verteilungsfreie Verfahren** bevorzugt, Normalitätstests (Shapiro-Wilk) nur als Diagnostik, Q-Q-Plots.
- Analyseplan wird vor Sichtung der echten Daten eingefroren (Tag im Git).

### 8.2 H1 – Kategorienvergleich
| Schritt | Verfahren |
|---|---|
| Deskription | Mittelwert ± SD je Kategorie und Last; Squat (n = 2 Stangen, 1 Modell) wird einzeln ausgewiesen |
| Test | Power (n = 9) vs. Deadlift (n = 3): Welch-t bzw. Mann-Whitney-U/Permutationstest (exakt, da n klein), einseitig gemäß gerichteter Hypothese begründen |
| Effektstärke | Hedges g bzw. Rang-biserielle Korrelation, Bootstrap-KI (Stangen als Resampling-Einheit) |
| Squat | Nur deskriptiv und Einzelfallvergleich (kein Inferenztest); Einschränkung explizit in der Discussion |
| Erklärung (explorativ) | Regression von log(Durchbiegung) auf log(Ø) und log(Länge); Erwartung aus Balkenmodell: Steifigkeit ∝ d⁴ |
| Mehrfach | Holm über Laststufen |

### 8.3 H2 – Linearität und Restverformung
- **Linearität:** pro Stange und Run OLS `Durchbiegung ~ Last`; Ausweis von R², Steigung (mm je 100 kg) mit KI, Residuenmuster, Test auf quadratischen Term (partieller F-Test) und AIC-Vergleich linear vs. quadratisch. Aggregation über Runs per gemischtem Modell nur als Option (Abschnitt 11, Roadmap-Stretch).
- **Restverformung:** Differenz Baseline nach Entlastung − Baseline vor Belastung je Stange und Run. Bewertung gegen MDC95 aus V5; Äquivalenztest (TOST) mit Grenze = MDC.
- Formulierung: H2 gilt für eine Stange als „nicht widerlegt“, wenn kein relevanter quadratischer Anteil und Restverformung innerhalb MDC. „Rein linear“ ist nicht beweisbar, es wird die Abwesenheit nachweisbarer Abweichung berichtet.
- Hinweis: Nur aufsteigende Beladung ⇒ Hysterese und Lastpfadabhängigkeit nicht prüfbar.

### 8.4 Reliabilität und Messunsicherheit
- ICC(2,1) (absolute Übereinstimmung), SEM = SD·√(1−ICC), MDC95 = 1,96·√2·SEM; CV je Stange und Last.
- Unsicherheitsbudget: Subpixel-Detektion, Skalenfehler, Verzerrungsrest, Markerneigung; Fortpflanzung per Monte-Carlo (10⁴ Ziehungen) auf D1–D4.

### 8.5 Software
NumPy, pandas, SciPy, statsmodels (Regression, F-Test, Mixed Models), pingouin oder eigene ICC-Implementierung (gegen Referenz getestet), OpenCV, matplotlib, SciencePlots, joblib. Zufallszahlen immer mit festem Seed aus der Config.

---

## 9. Nicht-funktionale Anforderungen

| Bereich | Anforderung |
|---|---|
| Reproduzierbarkeit | `uv.lock`, feste Seeds, Version/Commit-Hash und Config-Hash in jedem Output; Ergebnisse deterministisch |
| Performance | 700 Bilder in unter 10 min auf Laptop (joblib-Parallelisierung), Zwischenergebnisse gecacht |
| Qualität | pytest mit Tests auf synthetischen Daten (Bias-Grenzen als Regressionstest), ruff, Typannotationen; GitHub Actions läuft Lint + Tests |
| Nachvollziehbarkeit | Jede Zahl im Paper ist mit Skript + Daten-Hash rückverfolgbar |
| Datenschutz/Integrität | Keine Personen auf Fotos erforderlich; Gesichter ggf. zuschneiden. Manuelle Eingriffe werden geloggt |
| Doku | README und Methodik-Doku auf Deutsch, API/Code-Kommentare knapp, Plot-Texte Englisch |
| Plattform | Python 3.14 (Draft nennt 3.14.6). Falls OpenCV/SciPy-Wheels noch fehlen, Fallback auf 3.13 per Entscheidung festhalten |

---

## 10. Repo-, Daten- und Architekturkonzept

### 10.1 Umgang mit Bildern (Antwort auf deine Frage)
**Empfehlung: Rohbilder nicht in Git.** Bei ca. 700 Fotos à 5–10 MB sind das 3,5–7 GB; GitHub begrenzt einzelne Dateien auf 100 MB und rät zu deutlich kleineren Repos, Git-LFS hat nur ein kleines kostenloses Kontingent. Kombination aus lokal und GitHub:

| Was | Wo |
|---|---|
| Rohbilder (RAW/JPG) | Lokal + Backup (Uni-Cloud, externe Platte; später ggf. OSF/Zenodo bei Veröffentlichung) |
| Manifest mit Pfad, SHA-256, Metadaten | **Git** (`data/manifest.csv`, wenige KB) |
| Tidy-Ergebnisdaten (Koordinaten, Durchbiegungen) | **Git** (`data/derived/`, einige MB) |
| QC-Overlays | Lokal; nur eine kleine, herunterskalierte Auswahl für die Arbeit im Git |
| Synthetische Demo-Bilder | Werden von `simulate` erzeugt, nur Seed + Parameter im Git, Bilder in `.gitignore` |
| Spätere Option | DVC mit Remote-Speicher, falls Bilder versioniert geteilt werden sollen |

Das Manifest erlaubt, jedes Ergebnis einem exakten Bild zuzuordnen, ohne dass die Bilder im Repo liegen.

### 10.2 Struktur
```
barbellscan/
├── pyproject.toml, uv.lock, .python-version
├── config/            # bars.yaml, camera.yaml, analysis.yaml, markers.yaml
├── data/              # manifest.csv, derived/ (git), raw/ (gitignored)
├── docs/              # PRD.md, ROADMAP.md, Methodik, ADRs
├── src/barbellscan/
│   ├── config.py      # pydantic-Modelle für YAML
│   ├── io.py          # Manifest, Bilder, EXIF
│   ├── calibration.py # Intrinsics, Undistortion, Reprojektionsfehler
│   ├── detection.py   # ArUco (Hintergrund) / gelbe Kugeln / Tape
│   ├── geometry.py    # Homographie, Skala, Biegelinie
│   ├── deflection.py  # D1–D4, Unsicherheit
│   ├── qc.py          # Flags, Overlays, Bericht
│   ├── simulate.py    # synthetische Bilder (Ground Truth)
│   ├── beam_model.py  # Euler-Bernoulli
│   ├── stats/         # descriptive, linearity, categories, reliability
│   ├── plots.py, tables.py
│   └── cli.py
├── tests/
└── .github/workflows/ci.yml
```

### 10.3 Datenfluss
`Manifest + Fotos → Undistortion → Marker-Detektion → Skalierung/Rektifizierung → D1–D4 + Unsicherheit → Tidy-Dataset → Validierung + Statistik → Tabellen/Plots`

---

## 11. Außerhalb des Umfangs / Stretch

- Aufbau der Hardware, Fotoshooting, Schreiben der Arbeit.
- Physischer Referenzsensor (Messuhr/Laser) und Validität gegenüber einem Sensor (entfällt mit RQ2/H3).
- Dynamische Messung (Video, Whip während des Lifts).
- Stretch: Linear Mixed Models (Stange als Random Effect, Run genestet), Echtzeit-Tracking, Web-UI.

---

## 12. Risiken

| Risiko | Wirkung | Gegenmaßnahme |
|---|---|---|
| Fotos fehlen noch, Shooting verspätet (laut Plan CW 40) | Zeitdruck bei Intermediate Results | Pipeline vollständig auf Synthetik entwickeln, Echtdaten später nur „einstecken“ |
| Kleine Stichprobe (3 Deadlift-, 2 Squat-Exemplare) | Geringe Power, KIs breit | Exakte/Permutationstests, Effektstärken statt p-Wert-Fokus, ehrliche Limitation |
| **Tiefenversatz:** Hintergrund-ArUco liegt nicht in der Stangenebene | Skala um das Abbildungsverhältnis falsch; D1 skaliert proportional (5 % Versatz ⇒ 5 % Fehler, im Test bestätigt) | Marker möglichst in der Stangenebene (Ständer neben dem Monolift) oder Abstände messen und Korrekturfaktor in die Unsicherheit aufnehmen; Gegenprobe mit Referenzquadrat |
| **Verzerrung:** Ein einzelner Marker in Bildmitte erlaubt keine Schätzung der Linsenverzerrung, und die Kugeln liegen am Bildrand, wo sie am größten ist | Systematischer Fehler der Endpunkte | Intrinsische Kalibrierung vorab (ChArUco, FR-05), Marker nur für Skala und Plausibilität |
| **Hängende Kugeln:** Hängelänge verschiebt die Sehne nach unten (D1 + h), Pendeln addiert Rauschen | Systematischer Fehler | Kugel starr an der Kappe montieren, sonst `ball_hang_mm` messen und abziehen; Test vorhanden |
| Gelbe Kugeln: Reflexe, Verwechslung mit gelben Gegenständen im Hintergrund | Fehlerhafte Detektion | Mattes Gelb, Farbblobs plausibilisieren (Größe, genau zwei), QC-Flags |
| Kamerawinkel/Linse nicht fixiert | Perspektiv- und Skalierungsfehler | D1 statt absoluter Werte primär, Referenzquadrat/ArUco in jeder Aufnahme, Kalibrierprotokoll |
| Beleuchtung/Reflexe (glänzende Kugel, glänzender Schaft) | Detektionsausfälle | QC-Flags, manueller Override mit Log, Beleuchtungsvarianten in Synthetik testen |
| Durchbiegungen kleiner als Auflösung bei niedrigen Lasten | Rauschen dominiert | MDC ausweisen, niedrige Lasten nicht überinterpretieren |
| Re-Seating der Stange zwischen Runs | Streuung zwischen Runs | In Reliabilität bewusst enthalten, D1 ist davon weniger betroffen |
| Python-3.14-Wheels fehlen | Setup-Probleme | Früh prüfen, Fallback dokumentieren |
| Last 425 kg statt 525 kg | Frühere Draft-Aussagen/Plots nicht mehr gültig | Config-getriebene Laststufen, Dokumente anpassen |

---

## 13. Offene Entscheidungen und Inkonsistenzen in den Drafts

| # | Punkt | Empfehlung |
|---|---|---|
| O1 | Primäre Durchbiegungsdefinition (D1–D4) | D1 vorab einfrieren |
| O2 | ~~Markerwahl~~ **entschieden:** gelbe Kugeln an den Kappen, Elektroband in der Mitte, ArUco nur im Hintergrund | Umgesetzt in Simulator und Tracking |
| O8 | Abstand/Tiefe der ArUco-Ebene zur Stangenebene, Markergröße (Annahme 100 mm), Kugeldurchmesser (Annahme 50 mm) | Vor dem Shooting messen und in `config/analysis.yaml` eintragen |
| O9 | Kugeln starr oder hängend montiert (`ball_hang_mm`) | Starr bevorzugt |
| O10 | Plattenzähler/ID-Tafel (FR-31/32) übernehmen? Scheibendicke und -durchmesser der roten 25-kg-Scheiben, Klemmendicke messen (Simulator nimmt 28 mm, 450 mm, 30 mm an) | Entscheidung vor M3 |
| O3 | Genaue Anzahl Baseline-Fotos (1 pro Run? zusätzlich vor Run 1?) | Je Run eine Baseline vor Belastung (leere Stange) **und** eine nach Entlastung, sonst ist die Restverformung nicht messbar |
| O4 | Reihenfolge der Stangen und Runs (Randomisierung, Pausen, Temperatur) | Reihenfolge im Manifest erfassen, in Analyse als Kovariate prüfbar |
| O5 | Kamera, Auflösung, Abstand, Fixierung (Stativ) | Im Kalibrierprotokoll festhalten, EXIF mitlesen |
| O6 | Messbereich: 20 kg als erste Stufe, reale Stangengewichte 20 bzw. 25 kg (Squat-Bar 25 kg) | Eigengewicht je Stange in `bars.yaml` |
| O7 | Akzeptanzschwelle der Messunsicherheit | Nach V1 festlegen |

**Inkonsistenzen, die vor Abgabe zu bereinigen sind:**
0. Markerkonzept geändert: Concept Draft (Abschnitt 2.1, Figure 3/4), Slides (Folie 7) und das Creo-Modell (`kk.prt`, Slipring-Aufsatz) beschreiben noch ArUco an den Enden bzw. Kugel-/Slipring-Varianten; Methods muss auf gelbe Kugel + Hintergrund-ArUco umgeschrieben werden.
1. Concept Draft und Slides nennen 525 kg, 11 Laststufen und 715 Bilder; neu 425 kg, 9 Stufen. Außerdem steht im Zeitplan „520 kg barbell photoshoot“.
2. Slides führen RQ2/H3, das .docx nicht mehr.
3. H1 vergleicht gegen „Power und Squat“, aber Squat ist nur ein Modell (2 Exemplare), daher nicht inferenzstatistisch prüfbar.
4. Die Reihenfolge der Modelle weicht zwischen Table 1 und Table 2 ab (z. B. steht die Texas Power Bar in Table 1 an erster, in Table 2 an neunter Stelle); die 2 Squat-Exemplare sind in keiner Tabelle abgebildet.
5. Im .docx steht „Fehler! Verweisquelle konnte nicht gefunden werden“ und „Section 0“ (kaputte Querverweise).
6. Zugfestigkeit (PSI) wird in der Methodik als Materialeigenschaft für die „Whip“ angeführt; sie bestimmt die Plastizitätsgrenze, nicht die Steifigkeit (E-Modul). Das sollte für H1/H2 sauber getrennt werden.
7. Die Slides erwähnen „Red plate progression“ bis 525 kg; Lastplan mit 425 kg aktualisieren.
