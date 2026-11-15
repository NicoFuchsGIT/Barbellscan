# Analyseplan – Barbellscan (eingefroren vor der Datenauswertung)

| | |
|---|---|
| **Stand** | v1.0, 15.11.2026 |
| **Status** | Festgelegt **bevor** aus den echten Fotos eine Durchbiegung (D1/ΔD1) berechnet wurde. Bisher erfolgte nur eine Qualitätskontrolle (Vollständigkeit, Scheibenzahl, Schärfe, Kameraversatz, grobe Kugelpositionen). |
| **Änderungen** | Nur als datierter Nachtrag in Abschnitt 11 mit Begründung. Der Git-Commit dieser Datei gilt als Zeitstempel der Festlegung. |
| **Ersetzt** | Die Abschnitte 4, 5, 7 und 8 der [PRD](PRD.md) v0.2, soweit sie widersprechen. |

---

## 1. Datensatz

- **13 Stangen × 3 Zyklen (A, B, C) × 17 Fotos = 663 JPEGs** (Sony A7 III, FE 24-70 mm F4 ZA OSS, 6000 × 3376 px, F4, 1/15 s, ISO 400, Auslösung von Hand).
- Brennweite laut EXIF 41 mm, **TexasSquat 40 mm**. Kamerainterne Verzeichnungskorrektur bei beiden Brennweiten aktiv (EXIF `Sony:DistortionCorrection = Applied`, `DistortionCorrectionSetting = Auto`).
- Keine RAW-Dateien, keine Kalibrieraufnahmen.
- Rohbilder bleiben außerhalb des Git, Beweiskette über SHA-256 im Manifest (`data/manifest.csv`, abgeleitet aus `manifest_qc.csv`).

### Stangen und Kategorien

| bar_id | Foto-Präfix | Kategorie | Ringabstand (mm) |
|---|---|---|---|
| texas_power | TexasPower | power | 810 |
| ohio_power | OhioPower | power | 810 |
| ivanko_power | IvankoPower | power | 810 |
| leoko_power | LeokoPower | power | 810 |
| eleiko_comp_2016 | Eleiko2016Comp | power | 810 |
| eleiko_comp_2026 | Eleiko2026Comp | power | 810 |
| eleiko_training_2016 | Eleiko2016PowerTraining | power | 810 |
| eleiko_training_2026 | Eleiko2026PowerTraining | power | 810 |
| texas_deadlift | TexasDeadlift | deadlift | 810 |
| ohio_deadlift | OhioDeadlift | deadlift | 810 |
| bastard_deadlift | StrengthShopDeadlift | deadlift | 810 |
| texas_squat | TexasSquat | squat | 810 |
| zkc_iwf | ZKCIWF | weightlifting | 910 |

Power n = 8, Deadlift n = 3, Squat n = 1, Weightlifting n = 1. Alle 13 fotografierten Stangen gehen in die Auswertung ein.
Stammdaten (Länge, Durchmesser, Masse) sind Herstellerangaben. Wo die Bildvermessung widerspricht, gilt der Bildwert (siehe 9).

## 2. Versuchsablauf und Lastvariable

- Pro Zyklus 17 Stufen `step = 0 … 16`: 0 bis 8 Scheiben je Seite (`phase = up`) und zurück auf 0 (`phase = down`).
- **Lastvariable ist die Zusatzmasse** `added_mass_kg` (Scheiben und Klemmen, ohne Stangeneigengewicht):
  `0` bei 0 Scheiben, sonst `55 + 50·(n − 1)` mit n Scheiben je Seite, also 0, 55, 105, …, 405 kg.
  (Kalibrierte Eleiko 25-kg-Scheiben, 2 × 2,5 kg Klemmen ab der ersten Scheibe.)
- Endkappen wurden vor **jedem** Foto neu aufgesteckt; die gelben Bänder (Mitte, beide Ringmarkierungen) blieben während eines Zyklus kleben.
- Reihenfolge der Stangen nach Kategorie geblockt (Deadlift → Power → Squat), keine Wiederholungsmessung am Ende des Tages.

## 3. Messgeometrie

| Größe | Wert |
|---|---|
| Endmarker | Gelbe Kugel Ø 15 mm, fest auf der Achse der Kappe (`ball_hang_mm = 0`) |
| Kugelmitte | 35 mm hinter der Sleeve-Stirnfläche (Kappe BC-001) ⇒ Kugelabstand = L + 70 mm |
| Mittenmarker | Gelbes Band, 14 mm, an der gemessenen Stangenmitte |
| Ringmarker | Gelbe Bänder, 14 mm, mittig auf den Ringmarkierungen (±405 mm, ZKC ±455 mm) |
| Hooks | Innenkanten 650 mm, Außenkanten 725 mm. Auflage unter Last an den Außenkanten (±362,5 mm), leere Stange näher an den Innenkanten |
| Kamera | Höhe 126 cm (= Hook-Höhe), Abstand ≈ 3 m, ≈ 2,36 px/mm in der Stangenebene |
| Vorzeichen | positiv = Enden unter der Mitte |

## 4. Bildauswertung

1. **Detektion im Originalbild** in einer ROI um die Stange (schließt gelbe Monolift-Knöpfe aus). Keine Bildkopien, kein Drehen oder Entzerren der Bilder.
2. **Zuordnung der gelben Objekte:** Kugeln = die beiden äußersten Blobs mit zu Ø 15 mm passender Größe; Mittenband = Blob nächst der Kugelmitte; Ringbänder = die beiden übrigen Bänder.
3. **Subpixel-Zentroide** über gewichtete Bildmomente (wie M1).
4. **Verzeichnung:** Die JPEGs sind kameraseitig korrigiert. Primär **keine** weitere Korrektur. Restverzeichnung wird geprüft über (a) Plumb-Line an der Oberkante der Holzwand und der Monolift-Traverse, (b) Ringabstand 810 vs. 910 mm (ZKC), (c) Kugelabstände der 2200-mm-Stangen. Bei nachweisbarem Rest: Sensitivitätsanalyse mit Punktkorrektur (`cv2.undistortPoints`).
5. **QC-Overlay** für jedes Bild, alle Bilder werden visuell gesichtet.

## 5. Zielgrößen

**Skala** je Zyklus: Abstand der beiden Ringband-Zentroide in px (Mittel aus `step` 0 und 16) / nominaler Ringabstand. Gegenprobe: Kugelabstand / (L + 70 mm).

**D1** (je Bild): Senkrechter Abstand des Mittenband-Zentroids von der Sehne durch die beiden Kugelzentroide, in mm.

**ΔD1** (je Bild): `D1(step) − D1(step 0 desselben Zyklus)`. Entfernt Vorkrümmung, Kappensitz-Offset, Eigengewichtsbiegung; invariant gegen Kameraversatz, Bildrotation und starres Kippen der Stange.

| Rolle | Größe | Definition |
|---|---|---|
| **Primär** | Nachgiebigkeit c (mm/100 kg) bzw. scheinbare Steifigkeit k = 100/c (kg/mm) | Je Zyklus OLS `ΔD1 ~ added_mass` auf dem Belastungsast (step 0–8, Achsenabschnitt frei). Je Stange: c = Mittel der 3 Zyklen |
| Sekundär | ΔD1 bei 405 kg | step 8, Mittel der 3 Zyklen |
| Sekundär | ΔD_ring (längenbereinigt) | wie ΔD1, aber Sehne durch die beiden Ringbänder statt durch die Kugeln: Biegung im Bereich der Auflagen, unabhängig von Überhang und Kappe |

## 6. Statistik

### 6.1 Konfirmatorisch (einziger formaler Test)
**H1:** Deadlift-Stangen sind nachgiebiger als Power-Stangen.
- Analyseeinheit: physische Stange (c je Stange), Deadlift n = 3 vs. Power n = 8.
- Exakter einseitiger Permutationstest auf die Mittelwertdifferenz von c (alle 165 Zuordnungen), α = 0,05.
- Berichtet werden Mittelwertdifferenz, Hedges' g und der exakte p-Wert.
- Ein Test ⇒ keine Mehrfachtest-Korrektur.

### 6.2 Deskriptiv
- c, k, ΔD1(405) und ΔD_ring je Stange mit 95 %-KI aus den 3 Zyklen; Kategorie-Mittelwerte.
- **Innerhalb eines Typs:** Differenzen mit 95 %-KI (Welch), u. a. Eleiko Training 2016 vs. 2026 und Competition 2016 vs. 2026. Keine p-Werte.
- Squat und Weightlifting (je n = 1) nur deskriptiv; ZKC zusätzlich im Lastbereich ≤ 205 kg qualitativ neben Chiu (2010).
- Load-Deflection-Kurven je Stange (Belastung und Entlastung) und je Kategorie.

### 6.3 H2 – Elastizität (je Stange, bewertet gegen MDC95)
1. **Linearität:** quadratischer Term in OLS je Zyklus (Belastungsast). Kriterium: Beitrag des quadratischen Terms bei 405 kg ≤ MDC95.
2. **Restverformung:** ΔD1 bei step 16 (Mittel der 3 Zyklen); TOST mit Äquivalenzgrenze ±MDC95.
3. **Hysterese:** mittlere Differenz ΔD1(down) − ΔD1(up) bei gleicher Zusatzmasse (55–355 kg).

Formulierung im Ergebnis: „keine Abweichung oberhalb der Nachweisgrenze“, nicht „rein elastisch“.

### 6.4 Reliabilität und Messunsicherheit
- Zyklen sind austauschbare Wiederholungen ⇒ **ICC(1,1)**, SEM = √MS_within, MDC95 = 1,96 · √2 · SEM; für c und ΔD1(405).
- **Kappen-Neusitz** (vor jedem Foto) wird aus den Daten geschätzt: Residuen-SD der linearen Fits und Streuung der Kugeln relativ zu den Ringbändern bei Wiederholstufen (step 0 vs. 16, up vs. down).
- Unsicherheitsbudget: Detektion (Subpixel), Kappen-Neusitz, Skala (Bandplatzierung ±1 mm auf 810 mm, Detektion), Restverzeichnung (aus 4.4), Unschärfe. Fortpflanzung per Monte-Carlo (10⁴ Ziehungen, Seed aus `config/analysis.yaml`).

## 7. Umgang mit QC-Befunden

| Befund | Umgang primär | Sensitivitätsanalyse |
|---|---|---|
| `blur` (40 Bilder, Handauslösung) | eingeschlossen, geflaggt | ohne diese Bilder |
| `camera_shift` | eingeschlossen (ΔD1 invariant) | – |
| OhioDeadliftB9680, linke Kugel fehlt (Sleeve-Stirn sichtbar) | fehlender Wert (16 statt 17 Punkte) | Rekonstruktion: Sleeve-Achse aus den Kanten, Kugelmitte 35 mm vor der Stirnfläche, Flag `manual_reconstruction` |
| StrengthShopDeadliftC9766, Nachaufnahme (neu beladen) | eingeschlossen, geflaggt | ohne dieses Bild |
| TexasSquat 40 mm / Kugel am Bildrand | eigene Skala über Ringbänder; Overlay manuell prüfen | – |
| Detektionsausfall | fehlender Wert, kein Imputieren | – |
| Ausreißer | kein automatischer Ausschluss; Ausschluss nur bei dokumentiertem Detektionsfehler im Overlay | – |

## 8. Ergebnisse, die vor Sicht der Daten festgelegt sind

- Primär: c (k) je Stange; konfirmatorisch: H1 nach 6.1.
- Alle anderen Analysen sind deskriptiv bzw. Sensitivitätsanalysen und werden als solche berichtet.

## 9. Bekannte Abweichungen und Regeln

- **TexasDeadlift-Länge:** Herstellerangabe 2349,5 mm, Kugelabstand im Bild deutet auf ≈ 2306 mm. Regel: Ist der Ringabstand in px bei dieser Stange unauffällig, gilt die Bildlänge (Table 1 mit Fußnote); ist er ebenfalls ≈ 1,8 % kleiner, lag eine andere Kameradistanz vor und die Herstellerangabe bleibt.
- **Kamera nicht absolut fix** (Akkuwechsel, Handauslösung): Versatz ≤ 12 px; durch ΔD1 kompensiert.
- **Zoom bei TexasSquat 40 statt 41 mm:** eigene Skala über Ringbänder.
- **Reihenfolge nach Kategorie geblockt:** als Limitation berichtet (Stahl-E-Modul ≈ −0,03 %/K, Detektionsstabilität über die Baseline-Kugelabstände belegt).
- **Asymmetrie:** Rechtes Ende sinkt in allen Zyklen ≈ 9 % stärker ab, Roll ≈ −0,5°. Bilder werden nicht gedreht; ΔD1 ist invariant. Ursache (Hook-Nachgiebigkeit vs. Überhang) wird mit den Ringbändern deskriptiv untersucht.

## 10. Abweichungen gegenüber PRD v0.2

| PRD v0.2 | Jetzt |
|---|---|
| 14 Stangen × 5 Runs × 10 Fotos | 13 × 3 × 17 |
| Gesamtlast 20 … 425 kg | Zusatzmasse 0 … 405 kg |
| Primär D1 bei 425 kg | Primär Nachgiebigkeit c / Steifigkeit k aus ΔD1 |
| H1 inkl. Squat, H2 Restverformung | H1 nur Deadlift vs. Power; H2 in drei Teilen gegen MDC95 |
| ArUco-Skala, Magenta-Mittenband, Kugel Ø 50 mm | Skala über Ringbänder, gelbes Mittenband, Kugel Ø 15 mm |
| ChArUco-Kalibrierung | kamerainterne Korrektur + Plumb-Line-Prüfung |
| Auflage ±371 mm | Hooks 650/725 mm, Auflage unter Last ±362,5 mm |
| ICC(2,1) über 5 Runs | ICC(1,1) über 3 Zyklen |

## 11. Nachträge

**N1 (15.11.2026, vor Berechnung echter Durchbiegungen): Zuordnung der Marker geometrisch statt über die Blobgröße (betrifft 4.2).**
Umsetzung: Zuerst werden Ringbänder und Mittenband als drei fast kollineare gelbe Blobs gesucht (Mitte genau zwischen den äußeren, Abstand der äußeren ≈ Ringabstand × nominaler Maßstab ± 30 %). Die Kugeln sind dann je Seite der Blob, der der aus Ringabstand und Kugelabstand (L + 70 mm) vorhergesagten Position am nächsten liegt, in einem Fenster unterhalb der Ringlinie. Ohne Ringbänder: äußerstes Blobpaar mit passendem Abstand als Kugeln, Flag `missing_ring`.
Begründung: Bewegungsunschärfe (Handauslösung, 1/15 s) verändert Größe und Form der Blobs, und bei einer fehlenden Kugel (OhioDeadliftB9680) würde „die äußersten Blobs“ ein Ringband als Kugel wählen. Zielgrößen, Skala und Statistik bleiben unverändert.

**N2 (15.11.2026, vor Berechnung echter Durchbiegungen): Bänder messen die Schaftachse statt des Flächenschwerpunkts (betrifft 4.3).**
Anlass: An einzelnen Fotos hat sich ein Band gelöst und hängt unter dem Schaft herab (z. B. Mittenband, Beispielfoto vom 15.11.2026). Ein Lappen von 2–4 cm verschiebt den Schwerpunkt um 8–18 mm (Simulation) und damit D1 bzw. ΔD1.
Umsetzung, **für alle Bänder in allen Fotos gleich** (ein Methodenwechsel innerhalb eines Zyklus würde in ΔD1 einen Sprung erzeugen):
1. Je Spalte mit vollem Gelbanteil die Oberkante des Bandes aus der Fläche unter dem Gelbprofil (Subpixel; exakt bei Antialiasing und symmetrischer Unschärfe). Spalten, die erst an der Bandunterseite beginnen (nur Lappen), fallen heraus.
2. Gerade durch die Oberkanten → lokale Schaftneigung. Bandmittellinie aus dem Schwerpunkt der Zone zwischen Oberkante und Oberkante + Schaftradius (der Lappen hängt darunter).
3. Messpunkt = Schnitt Bandmittellinie/Oberkante, verschoben um r = d/2 + Bandstärke (0,15 mm, Annahme) senkrecht zur Schaftrichtung. Der Radius in px kommt aus dem Ringabstand im selben Bild.
4. Flag `tape_hanging_<marker>`, wenn das Band höher als 1,3 × (d + 2 · Bandstärke) ist.
Konstante Restfehler (Annahme Bandstärke, Schattierung der Oberkante) kürzen sich in ΔD1 und ΔD_ring heraus.
Sensitivitätsanalyse: Die bisherige Schwerpunktmethode wird weiter berechnet (`d1_px_centroid`, `delta_d1_centroid_mm`, `compliance_centroid_mm_per_100kg`). Validierung auf Synthetik: Achse auf ≤ 0,2 px (x) bzw. ≤ 0,05 px (y), D1-Fehler ≤ 0,05 mm, auch mit 40 mm Lappen und geneigtem Schaft.

**N3 (15.11.2026, vor Berechnung echter Durchbiegungen): Linearität gegen das Lastmoment und an ΔD_ring (betrifft 6.3 Nr. 1).**
Anlass: Jede weitere Scheibe sitzt um eine Scheibendicke (27 mm) weiter außen, der Hebelarm der Last wächst also mit der Scheibenzahl. Ein ideal elastischer Balken (Euler-Bernoulli, Auflager ±362,5 mm) ist deshalb gegen die Zusatzmasse gekrümmt: Power-Stange 9,5 mm/100 kg bei der ersten und 16,8 mm/100 kg bei der letzten Stufe, Abweichung von der Geraden rund 2,5 mm. Das ursprüngliche Kriterium (quadratischer Term von ΔD1 gegen die Masse ≤ MDC95) wäre rein geometrisch verletzt und sagt nichts über das Material.
Umsetzung:
1. Regressor ist das **Lastmoment** um die Auflager, `M = 2 · Σ mᵢ · (xᵢ − 362,5 mm)` in kg·m, mit dem Scheibenschwerpunkt `xᵢ = Sleeve-Anschlag + (i − ½) · 27 mm` und der Klemme 15 mm hinter der letzten Scheibe (`load_moment_kgm`; Scheibendicke und Klemmenlage sind Annahmen in `config/analysis.yaml` und werden nachgemessen).
2. Zielgröße des Kriteriums ist **ΔD_ring** (Sehne durch die Ringbänder). Zwischen den Auflagern ist das Biegemoment nach der Statik genau M · g, unabhängig von Überhang, Sleeve-Lagerung und Kappe; ΔD_ring ist dort exakt proportional zu M (Balkenmodell: Abweichung < 0,01 mm).
3. Kriterium: Differenz zwischen quadratischem und linearem Fit von ΔD_ring gegen M bei 8 Scheiben (Belastungsast, Mittel der 3 Zyklen) ≤ MDC95 von ΔD_ring(405 kg).
4. Deskriptiv weiter berichtet: dieselbe Größe für ΔD1 gegen M (`nonlin_d1_moment_mm`; enthält die Biegung im Lastbereich und ist auch im Modell nicht null, 0,3–0,7 mm) und für ΔD1 gegen die Masse (`nonlin_at_peak_mm`).
Unverändert: primäre Zielgröße c (OLS von ΔD1 gegen die Zusatzmasse) und H1. c ist damit eine scheinbare Nachgiebigkeit für genau dieses Beladungsschema; der Vergleich zwischen den Stangen bleibt gültig, weil alle gleich beladen wurden.
Grenze: Das Moment setzt die Auflage an den Hook-Außenkanten voraus. Liegt die Stange bei kleiner Last weiter innen auf, entsteht bei den ersten Stufen eine kleine Abweichung; sie wird über eine Sensitivitätsrechnung mit ±325 mm abgeschätzt.

**N4 (15.11.2026): Ausschlussliste (Klarstellung zu Abschnitt 7, keine neue Regel).**
Bilder mit dokumentiertem Detektionsfehler stehen mit Begründung in `data/exclusions.csv` (`image, reason`) und werden als fehlender Wert behandelt (`exclusion_reason`, Flag `excluded`). Sensitivitätsanalysen ohne geflaggte Bilder laufen über `deflect --drop-qc-flag <flag>`.
