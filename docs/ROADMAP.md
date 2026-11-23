# Roadmap – Barbellscan

Stand: 23.11.2026 (CW 48). Maßgeblich für Inhalt und Methode ist der [Analyseplan](ANALYSIS_PLAN.md) v1.0 mit den Nachträgen N1–N5; diese Roadmap regelt nur Reihenfolge und Termine. Die ursprüngliche Planung (14 Stangen × 5 Runs × 10 Fotos, ArUco-Skala, ChArUco-Kalibrierung) ist überholt und steht in der Git-Historie.

## Fixtermine

| Termin | CW |
|---|---|
| Zwischenpräsentation 2 (erste echte Ergebnisse H1/H2 mit Messunsicherheit) | 48 |
| Upload | 1 |
| Review-Feedback | bis 3 |
| Finale Version | 4 |

## Stand

| Baustein | Status |
|---|---|
| Projekt-Setup, Config, CI (M0) | ✅ |
| Simulator, Detektion gelber Marker (M1, N1, N2) | ✅ auf Synthetik |
| Fotos (13 × 3 × 17 = 663), QC, Manifest mit SHA-256 | ✅ |
| Analyseplan eingefroren | ✅ (Git-Tag `analysis-plan-v1` fehlt noch) |
| `track` (Bänder als Schwerpunkt in der Schaftzone, N5) auf den echten Fotos | ✅ 663/663 ausgewertet, 1 Kugel fehlt (bekannt) |
| `deflect`: Skala aus den Ringbändern, D1, ΔD1, ΔD_ring, Lastmoment, Kenngrößen je Zyklus | ✅ 662/663 Bilder mit ΔD1, Ergebnisse in `data/derived/` |
| Ausschlussliste und Sensitivitätsläufe (`data/exclusions.csv`, `--drop-qc-flag`) | ✅ Mechanik vorhanden, Liste noch leer |
| Statistik nach Plan 6: H1, Deskriptiv, H2, ICC/SEM/MDC95 (`stats`) | ✅ gegen Referenzwerte getestet, auf Echtdaten gelaufen |
| Abbildungen (`plot` → `data/plots/`): Kurven je Stange, Nachgiebigkeit, H1, H2 | ✅ |
| **Sichtung aller Overlays, Nachmessen von Kugelversatz, Bandabstand und Scheibendicke** | ❌ nächster Schritt |
| Plumb-Line-Prüfung der Restverzeichnung (Plan 4.4) | ❌ |
| Unsicherheitsbudget mit Monte-Carlo (Plan 6.4) | ❌ |
| Sensitivitätsläufe (ohne `blur`, Oberkanten-Methode N2, Auflage ±325 mm) | ❌ |
| Balkenmodell als Gegenprobe (V4) | ❌ (Rechenkern liegt als Testhilfe in `tests/test_stats.py`) |
| Tabellen fürs Paper als LaTeX, alles aus einem Befehl (`report`) | ❌ |

## Erste Ergebnisse (vorläufig, vor Overlay-Sichtung und Nachmessung)

| Größe | Wert |
|---|---|
| H1: Nachgiebigkeit Deadlift − Power | +11,0 mm/100 kg (25,4 vs. 14,4), exakter Permutationstest p = 0,006 (165 Permutationen), Hedges' g = 8,9 |
| Reliabilität der Nachgiebigkeit | SEM 0,10 mm/100 kg, MDC95 0,28 mm/100 kg |
| H2 | Nichtlinearität, Restverformung und Hysterese im Mittel bei allen Stangen innerhalb MDC95; KI der Hysterese von Eleiko Training 2026 reicht darüber hinaus |

Die Zahlen hängen an Annahmen in `config/analysis.yaml` (Kugelversatz 35 mm, Scheibendicke 27 mm, Bandstärke 0,15 mm). Nach dem Nachmessen `deflect`, `stats` und `plot` neu laufen lassen.

Geprüft in Echtgröße (6000 × 3376 px, 2,36 px/mm, echte ROI, Roll −0,5°, alle 13 Stangen): D1-Fehler ≤ 0,02 mm, auch mit 21 px vertikaler Bewegungsunschärfe und mit der kürzeren Texas-Deadlift-Stange. Das gilt für dunklen, neutralen Hintergrund ohne Linsenverzeichnung.

## Prüfpunkte für die Overlay-Sichtung

| Risiko | Befund auf Synthetik | Maßnahme |
|---|---|---|
| Gelblicher Hintergrund (Holz) hinter Schaft oder Kugeln | Gelbanteil ≥ 0,15: Bänder verschmelzen mit der Wand, D1 um 87 mm falsch (Flag `missing_ring`). Knapp darunter: Bandoberkante 1,2 px zu hoch (0,5 mm), **ohne Flag** | Laut Aufbau ist der Hintergrund dunkel. Im Pilot die Overlays der Bänder prüfen; falls nötig lokaler Hintergrundabzug als Nachtrag |
| Kugel am Bildrand angeschnitten (TexasSquat, 51 Bilder `ball_near_edge`) | 20 px Anschnitt: Kugel 5 px seitlich falsch, ohne Flag; Wirkung auf D1 0,02 mm | Overlays der 51 Bilder sichten (Plan 7); Rand-Flag bei Bedarf nachrüsten |
| Fehlendes Baseline-Foto (step 0) | Der ganze Zyklus verliert ΔD1 (`no_baseline`) | Im Echtdatenlauf kein Fall: alle 39 Zyklen haben eine Baseline |
| ROI und Gelbschwelle sind geschätzt | Echtdatenlauf: 663/663 Bilder erkannt | Bei Auffälligkeiten in der Sichtung mit `overlay` nachjustieren und `track` neu laufen lassen |

## Nächste Schritte

### CW 48: Präsentation 2 und Abschluss Echtdaten (M4)
1. Git-Tag `analysis-plan-v1` auf den Commit setzen, der den Plan eingefroren hat (`9e5612a`); die Nachträge N1–N5 sind datiert und in der Git-Historie nachvollziehbar.
2. Alle Overlays sichten (zuerst die Bilder mit Flags in `tracking.csv` und die 51 TexasSquat-Bilder mit `ball_near_edge`), Detektionsfehler mit Begründung in `data/exclusions.csv`.
3. Kugelversatz, Ringbandabstand, Scheibendicke, Klemmenlage und Bandstärke nachmessen, in `config/analysis.yaml` eintragen.
4. `deflect`, `stats`, `plot` neu, Ergebnisse committen.
5. Folien: H1 (`h1_groups.png`), Kurven je Stange (`load_deflection_grid.png`), H2 gegen MDC95 (`h2_elasticity.png`).

**Fertig, wenn:** jedes geflaggte Bild nachvollziehbar behandelt ist und die Config keine Annahmen mehr enthält.

### CW 48–49: Validierung und Unsicherheit (M5)
1. Plumb-Line-Prüfung (Wandoberkante, Monolift-Traverse), Ringabstand 810 vs. 910 mm, Kugelabstände der 2200-mm-Stangen (Plan 4.4).
2. Kappen-Neusitz aus den Daten schätzen (Residuen-SD, Kugeln relativ zu den Ringbändern).
3. Unsicherheitsbudget mit Monte-Carlo (10⁴ Ziehungen, Seed aus der Config).
4. Sensitivitätsläufe: ohne `blur`, ohne StrengthShopDeadliftC9766, Oberkanten-Methode (N2), Auflage ±325 mm.
5. Regel zur TexasDeadlift-Länge anwenden (Plan 9).

**Fertig, wenn:** die Messunsicherheit (95 %) bekannt ist und H1/H2 mit ihr berichtet werden können.

### CW 49–51: Paper-Outputs (M7)
- Table 2 und Statistik-Tabellen als LaTeX; die Abbildungen gibt es bereits (`plot`), sie wandern in `report`.
- Balkenmodell als Gegenprobe (V4), ZKC ≤ 205 kg neben Chiu (2010).
- Methodik-Doku und Anleitung zur Reproduktion.

**Fertig, wenn:** alle Abbildungen und Tabellen der Arbeit aus einem Befehl (`barbellscan report`) entstehen.

### CW 52–4: Freeze und Abgabe (M8)
- Reproduktionslauf auf sauberem Checkout, Abgleich aller Zahlen im Manuskript.
- Release-Tag `v1.0-seminar`, `CITATION.cff`, Data-/Software-Availability-Statement.
- Review-Feedback einarbeiten.

## Priorisierung bei Engpass
1. **Unverzichtbar:** Overlay-Sichtung und Nachmessen, c je Stange, H1, ICC/MDC95, Kurven, Table 2.
2. **Wichtig:** H2 gegen MDC95, Plumb-Line, Unsicherheitsbudget, Sensitivitätsläufe.
3. **Zuerst streichbar:** Balkenmodell-Vergleich, ΔD_ring-Auswertung der Asymmetrie, LaTeX-Export.

## Offene Punkte außerhalb des Codes
- Scheibendicke (Annahme 27 mm), Klemmenlage und Bandstärke (Annahme 0,15 mm) nachmessen.
- `ohio_power` fehlt noch in Table 1 des Manuskripts.
- Concept Draft und Slides an 13 × 3 × 17, Zusatzmasse 0–405 kg und H1/H2 laut Analyseplan angleichen.
