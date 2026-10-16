"""Durchbiegung aus Markerpunkten (PRD 5.3). In M1 nur D1."""

from __future__ import annotations

import numpy as np


def d1_mm(
    left_px: tuple[float, float],
    right_px: tuple[float, float],
    centre_px: tuple[float, float],
    scale_px_per_mm: float,
) -> float:
    """D1: Abstand der Mitte zur Sehne der Endmarker, senkrecht zur Sehne (rollinvariant).

    Positiv, wenn die Enden unter der Mitte liegen (Bildkoordinaten: y nach unten).
    """
    left, right, centre = (np.asarray(p, float) for p in (left_px, right_px, centre_px))
    u = right - left
    u = u / np.linalg.norm(u)
    n = np.array([-u[1], u[0]])  # zeigt bei u = (1, 0) nach unten (+y)
    return float(n @ (left - centre)) / scale_px_per_mm
