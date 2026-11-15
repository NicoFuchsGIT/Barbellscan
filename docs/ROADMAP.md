# Roadmap – Barbellscan

Stand: 15.11.2026 (CW 46). Maßgeblich für Inhalt und Methode ist der [Analyseplan](ANALYSIS_PLAN.md) v1.0 mit den Nachträgen N1–N5; diese Roadmap regelt nur Reihenfolge und Termine. Die ursprüngliche Planung (14 Stangen × 5 Runs × 10 Fotos, ArUco-Skala, ChArUco-Kalibrierung) ist überholt und steht in der Git-Historie.

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
| Simulator, Detektion gelber Marker, Schaftachse aus der Bandoberkante (M1, N1, N2) | ✅ auf Synthetik |
| Fotos (13 × 3 × 17 = 663), QC, Manifest mit SHA-256 | ✅ |
| Analyseplan eingefroren | ✅ (Git-Tag `analysis-plan-v1` fehlt noch) |
| `track`, `deflect`: Skala aus den Ringbändern, D1, ΔD1, ΔD_ring, Kenngrößen je Zyklus | ✅ auf Synthetik |
| Ausschlussliste und Sensitivitätsläufe (`data/exclusions.csv`, `--drop-qc-flag`) | ✅ |
| Statistik nach Plan 6: H1, Deskriptiv, H2, ICC/SEM/MDC95 (`stats`) | ✅ gegen Referenzwerte getestet |
| Pilotlauf der Detektion auf den echten Fotos | ✅ 663/663 ausgewertet, 1 Kugel fehlt (bekannt); Bandmessung danach umgestellt (N5) |
| `track` mit N5, `deflect`, `stats` auf den echten Fotos | ✅ 662/663 Bilder mit ΔD1, Ergebnisse in `data/derived/` |
| **Sichtung aller Overlays, Nachmessen von Kugelversatz, Bandabstand und Scheibendicke** | ❌ nächster Schritt |
| Plumb-Line-Prüfung der Restverzeichnung (Plan 4.4) | ❌ |
| Unsicherheitsbudget mit Monte-Carlo (Plan 6.4) | ❌ |
| Balkenmodell als Gegenprobe (V4) | ❌ (Rechenkern liegt als Testhilfe in `tests/test_stats.py`) |
| Abbildungen (`plot` → `data/plots/`): Kurven je Stange, Nachgiebigkeit, H1, H2 | ✅ |
| Tabellen fürs Paper als LaTeX, alles aus einem Befehl (`report`) | ❌ |

Geprüft in Echtgröße (6000 × 3376 px, 2,36 px/mm, echte ROI, Roll −0,5°, alle 13 Stangen): D1-Fehler ≤ 0,02 mm, auch mit 21 px vertikaler Bewegungsunschärfe und mit der kürzeren Texas-Deadlift-Stange. Das gilt für dunklen, neutralen Hintergrund ohne Linsenverzeichnung.

## Bekannte Risiken für den Pilotlauf

| Risiko | Befund auf Synthetik | Maßnahme |
|---|---|---|
| Gelblicher Hintergrund (Holz) hinter Schaft oder Kugeln | Gelbanteil ≥ 0,15: Bänder verschmelzen mit der Wand, D1 um 87 mm falsch (Flag `missing_ring`). Knapp darunter: Bandoberkante 1,2 px zu hoch (0,5 mm), **ohne Flag** | Laut Aufbau ist der Hintergrund dunkel. Im Pilot die Overlays der Bänder prüfen; falls nötig lokaler Hintergrundabzug als Nachtrag |
| Kugel am Bildrand angeschnitten (TexasSquat, 51 Bilder `ball_near_edge`) | 20 px Anschnitt: Kugel 5 px seitlich falsch, ohne Flag; Wirkung auf D1 0,02 mm | Overlays der 51 Bilder sichten (Plan 7); Rand-Flag bei Bedarf nachrüsten |
| Fehlendes Baseline-Foto (step 0) | Der ganze Zyklus verliert ΔD1 (`no_baseline`) | Bisher kein Fall bekannt; step-0-Fotos im Pilot zuerst prüfen |
| ROI und Gelbschwelle sind geschätzt | – | Mit `overlay` an einem Foto je Stange justieren, bevor `track` über alle läuft |

## Nächste Schritte

### CW 46–47: Echtdaten (M4)
1. Git-Tag `analysis-plan-v1` auf den Stand mit N1–N4 setzen, **bevor** `deflect` auf echten Daten läuft.
2. `check-manifest --verify`, dann `overlay` an je einem Foto pro Stange (leer und 8 Scheiben), ROI und Gelbschwelle festlegen.
3. `track` mit `--overlay-dir` über alle 663 Bilder, alle Overlays sichten, Detektionsfehler mit Begründung in `data/exclusions.csv` eintragen.
4. Scheibendicke und Klemmenlage nachmessen und in `config/analysis.yaml` eintragen (für das Lastmoment, N3).
5. `deflect`, `stats`; Ergebnisse nach `data/derived/` committen.

**Fertig, wenn:** ≥ 95 % der Bilder ohne manuellen Eingriff erkannt sind und jedes geflaggte Bild nachvollziehbar behandelt ist.

### CW 47–48: Validierung und Unsicherheit (M5), Präsentation 2
1. Plumb-Line-Prüfung (Wandoberkante, Monolift-Traverse), Ringabstand 810 vs. 910 mm, Kugelabstände der 2200-mm-Stangen (Plan 4.4).
2. Kappen-Neusitz aus den Daten schätzen (Residuen-SD, Kugeln relativ zu den Ringbändern).
3. Unsicherheitsbudget mit Monte-Carlo (10⁴ Ziehungen, Seed aus der Config).
4. Sensitivitätsläufe: ohne `blur`, ohne StrengthShopDeadliftC9766, Schwerpunktmethode, Auflage ±325 mm.
5. Regel zur TexasDeadlift-Länge anwenden (Plan 9).
6. Folien für CW 48: H1, Kurven je Stange, H2 gegen MDC95.

**Fertig, wenn:** die Messunsicherheit (95 %) bekannt ist und H1/H2 mit ihr berichtet werden können.

### CW 49–51: Paper-Outputs (M7)
- Table 2, Load-Deflection-Kurven (Belastung und Entlastung) je Stange und Kategorie, Statistik-Tabellen als CSV/LaTeX, einheitlicher Stil, englische Labels.
- Balkenmodell als Gegenprobe (V4), ZKC ≤ 205 kg neben Chiu (2010).
- Methodik-Doku und Anleitung zur Reproduktion.

**Fertig, wenn:** alle Abbildungen und Tabellen der Arbeit aus einem Befehl (`barbellscan report`) entstehen.

### CW 52–4: Freeze und Abgabe (M8)
- Reproduktionslauf auf sauberem Checkout, Abgleich aller Zahlen im Manuskript.
- Release-Tag `v1.0-seminar`, `CITATION.cff`, Data-/Software-Availability-Statement.
- Review-Feedback einarbeiten.

## Priorisierung bei Engpass
1. **Unverzichtbar:** Pilotlauf mit Overlay-Sichtung, c je Stange, H1, ICC/MDC95, Kurven, Table 2.
2. **Wichtig:** H2 gegen MDC95, Plumb-Line, Unsicherheitsbudget, Sensitivitätsläufe.
3. **Zuerst streichbar:** Balkenmodell-Vergleich, ΔD_ring-Auswertung der Asymmetrie, LaTeX-Export.

## Offene Punkte außerhalb des Codes
- Scheibendicke (Annahme 27 mm), Klemmenlage und Bandstärke (Annahme 0,15 mm) nachmessen.
- `ohio_power` fehlt noch in Table 1 des Manuskripts.
- Concept Draft und Slides an 13 × 3 × 17, Zusatzmasse 0–405 kg und H1/H2 laut Analyseplan angleichen.
