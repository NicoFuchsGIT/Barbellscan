"""Marker-Detektion: ArUco-Referenz (Hintergrund), gelbe Kugeln (Enden), Klebeband (Mitte)."""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from .simulate import ARUCO_DICT, ARUCO_ID


@dataclass
class ArucoHit:
    centre_px: tuple[float, float]
    side_px: float  # mittlere Kantenlänge
    roll_deg: float  # Neigung der Markerkante gegen die Bildhorizontale


def make_detector() -> cv2.aruco.ArucoDetector:
    params = cv2.aruco.DetectorParameters()
    params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
    params.cornerRefinementWinSize = 5
    params.cornerRefinementMaxIterations = 100
    params.cornerRefinementMinAccuracy = 0.005
    return cv2.aruco.ArucoDetector(cv2.aruco.getPredefinedDictionary(ARUCO_DICT), params)


def detect_aruco(
    image: np.ndarray, detector: cv2.aruco.ArucoDetector | None = None
) -> ArucoHit | None:
    """Referenzmarker (ID 0) im Hintergrund; None, wenn nicht gefunden."""
    detector = detector or make_detector()
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    corners, ids, _ = detector.detectMarkers(gray)
    if ids is None:
        return None
    for marker_id, c in zip(ids.ravel(), corners, strict=True):
        if int(marker_id) == ARUCO_ID:
            c = c.reshape(4, 2).astype(np.float64)
            sides = np.linalg.norm(c - np.roll(c, -1, axis=0), axis=1)
            top = c[1] - c[0]
            return ArucoHit(
                tuple(c.mean(axis=0)),
                float(sides.mean()),
                float(np.degrees(np.arctan2(top[1], top[0]))),
            )
    return None


def _roi_centroid(
    w: np.ndarray, mask: np.ndarray, pad: int = 8
) -> tuple[tuple[float, float], float] | None:
    """Schwerpunkt ohne Schwellwert in einer Region um den Blob.

    Ein harter Schwellwert würde die Ränder je nach Subpixel-Lage verschieden abschneiden
    (Sägezahn-Fehler mit 1 px Periode); die lineare Gewichtung bleibt dagegen unverzerrt.
    """
    x, y, bw, bh = cv2.boundingRect(mask)
    if bw == 0:
        return None
    h, wd = w.shape
    x0, y0, x1, y1 = max(x - pad, 0), max(y - pad, 0), min(x + bw + pad, wd), min(y + bh + pad, h)
    # Negative Gewichte (Stahl, dunkle Flächen) abschneiden: sie liegen fern der Blobränder und
    # würden den Schwerpunkt zur Seite ziehen; die positiven Randanteile bleiben unverändert.
    roi = np.maximum(w[y0:y1, x0:x1].astype(np.float64), 0.0)
    m = cv2.moments(roi)
    if m["m00"] <= 0:
        return None
    return (x0 + m["m10"] / m["m00"], y0 + m["m01"] / m["m00"]), float(m["m00"])


def detect_balls(
    image: np.ndarray, min_area_px: float = 100.0
) -> dict[str, tuple[tuple[float, float], float]]:
    """Gelbe Kugeln: Subpixel-Zentroid je Blob (gewichtete Momente), links/rechts nach x.

    Gewicht = Gelbanteil je Pixel (min(R, G) - B). Es werden die zwei größten Blobs verwendet;
    bei weniger als zwei Treffern fehlen die Einträge.
    """
    img = image.astype(np.float32)
    b, g, r = img[..., 0], img[..., 1], img[..., 2]
    w = (np.minimum(r, g) - b) / 255.0
    blob_mask = (w > 0.15).astype(np.uint8)  # nur zur Blobsuche
    n, labels, stats, _ = cv2.connectedComponentsWithStats(blob_mask, connectivity=8)
    blobs = sorted(
        (i for i in range(1, n) if stats[i, cv2.CC_STAT_AREA] >= min_area_px),
        key=lambda i: -stats[i, cv2.CC_STAT_AREA],
    )[:2]
    found = []
    for i in blobs:
        res = _roi_centroid(w, (labels == i).astype(np.uint8))
        if res:
            found.append(res)
    if len(found) != 2:
        return {}
    found.sort(key=lambda t: t[0][0])
    return {"left": found[0], "right": found[1]}


def detect_tape(
    image: np.ndarray, min_area_px: float = 50.0
) -> tuple[tuple[float, float], float] | None:
    """Subpixel-Zentroid des magentafarbenen Klebebands (gewichtete Bildmomente in einer ROI).

    Gewicht = Magenta-Anteil je Pixel (min(R, B) - G), antialiaste Ränder tragen anteilig bei.
    Gibt (Zentroid, Fläche in px) oder None zurück.
    """
    img = image.astype(np.float32)
    b, g, r = img[..., 0], img[..., 1], img[..., 2]
    w = (np.minimum(r, b) - g) / 255.0
    mask = (w > 0.15).astype(np.uint8)
    n, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    if n < 2:
        return None
    biggest = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    if stats[biggest, cv2.CC_STAT_AREA] < min_area_px:
        return None
    return _roi_centroid(w, (labels == biggest).astype(np.uint8))
