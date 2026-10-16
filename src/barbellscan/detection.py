"""Marker-Detektion: ArUco an den Sleeve-Enden, farbiges Klebeband in der Mitte (FR-06, FR-08)."""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from .simulate import ARUCO_DICT, MARKER_IDS


@dataclass
class ArucoHit:
    centre_px: tuple[float, float]
    side_px: float  # mittlere Kantenlänge


def make_detector() -> cv2.aruco.ArucoDetector:
    params = cv2.aruco.DetectorParameters()
    params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
    params.cornerRefinementWinSize = 5
    params.cornerRefinementMaxIterations = 100
    params.cornerRefinementMinAccuracy = 0.005
    return cv2.aruco.ArucoDetector(cv2.aruco.getPredefinedDictionary(ARUCO_DICT), params)


def detect_aruco(
    image: np.ndarray, detector: cv2.aruco.ArucoDetector | None = None
) -> dict[str, ArucoHit]:
    """Liefert Treffer für ``left``/``right``; fehlende Marker fehlen im Ergebnis."""
    detector = detector or make_detector()
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    corners, ids, _ = detector.detectMarkers(gray)
    hits: dict[str, ArucoHit] = {}
    if ids is None:
        return hits
    by_id = {
        int(i): c.reshape(4, 2).astype(np.float64)
        for i, c in zip(ids.ravel(), corners, strict=True)
    }
    for name, mid in MARKER_IDS.items():
        if mid in by_id:
            c = by_id[mid]
            sides = np.linalg.norm(c - np.roll(c, -1, axis=0), axis=1)
            hits[name] = ArucoHit(tuple(c.mean(axis=0)), float(sides.mean()))
    return hits


def detect_tape(
    image: np.ndarray, min_area_px: float = 50.0
) -> tuple[tuple[float, float], float] | None:
    """Subpixel-Zentroid des magentafarbenen Klebebands (gewichtete Bildmomente).

    Gewicht = Magenta-Anteil je Pixel (min(R, B) - G), antialiaste Ränder tragen anteilig bei.
    Gibt (Zentroid, Fläche in px) oder None zurück.
    """
    img = image.astype(np.float32)
    b, g, r = img[..., 0], img[..., 1], img[..., 2]
    w = (np.minimum(r, b) - g) / 255.0
    w[w < 0.15] = 0.0
    m = cv2.moments(w.astype(np.float64))
    if m["m00"] < min_area_px:
        return None
    return (m["m10"] / m["m00"], m["m01"] / m["m00"]), float(m["m00"])
