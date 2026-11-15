"""Pydantic-Modelle für die YAML-Konfiguration (config/*.yaml)."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, model_validator

Category = Literal["power", "deadlift", "squat", "weightlifting"]
Phase = Literal["up", "down"]


class Bar(BaseModel):
    bar_id: str
    photo_prefix: str
    name: str
    manufacturer: str | None = None
    article: str | None = None
    category: Category
    mass_kg: float = Field(gt=0)
    shaft_diameter_mm: float = Field(gt=0)
    total_length_mm: float = Field(gt=0)
    shaft_length_mm: float = Field(gt=0)
    ring_spacing_mm: float = Field(gt=0)
    note: str | None = None

    @model_validator(mode="after")
    def _plausible_lengths(self) -> Bar:
        if not self.ring_spacing_mm < self.shaft_length_mm < self.total_length_mm:
            raise ValueError(f"{self.bar_id}: erwartet Ringabstand < Schaft < Gesamtlänge")
        return self

    def ball_span_mm(self, ball_offset_mm: float) -> float:
        """Nomineller Abstand der Kugelmitten (Gesamtlänge + 2 x Kugelversatz)."""
        return self.total_length_mm + 2.0 * ball_offset_mm


class BarCatalog(BaseModel):
    bars: list[Bar]

    @model_validator(mode="after")
    def _unique(self) -> BarCatalog:
        for attr in ("bar_id", "photo_prefix"):
            vals = [getattr(b, attr) for b in self.bars]
            if len(vals) != len(set(vals)):
                raise ValueError(f"{attr} muss eindeutig sein")
        return self

    def bar_ids(self) -> list[str]:
        return [b.bar_id for b in self.bars]

    def bar(self, bar_id: str) -> Bar:
        for b in self.bars:
            if b.bar_id == bar_id:
                return b
        raise KeyError(bar_id)

    def by_prefix(self, photo_prefix: str) -> Bar:
        for b in self.bars:
            if b.photo_prefix == photo_prefix:
                return b
        raise KeyError(photo_prefix)


class Geometry(BaseModel):
    hook_inner_mm: float = Field(default=650.0, gt=0)
    hook_outer_mm: float = Field(default=725.0, gt=0)
    ball_diameter_mm: float = Field(default=15.0, gt=0)
    ball_offset_mm: float = Field(default=35.0, ge=0)
    tape_width_mm: float = Field(default=14.0, gt=0)
    tape_thickness_mm: float = Field(default=0.15, ge=0)

    @property
    def support_offset_loaded_mm(self) -> float:
        """Auflage unter Last an den Hook-Außenkanten."""
        return self.hook_outer_mm / 2.0


class Detection(BaseModel):
    nominal_px_per_mm: float = Field(default=2.36, gt=0)
    scale_tolerance: float = Field(default=0.3, gt=0, lt=1)
    roi_frac: tuple[float, float, float, float] | None = None
    yellow_threshold: float = Field(default=0.15, gt=0, lt=1)

    @model_validator(mode="after")
    def _roi_ordered(self) -> Detection:
        if self.roi_frac is not None:
            x0, y0, x1, y1 = self.roi_frac
            if not (0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1):
                raise ValueError("roi_frac: 0 <= x0 < x1 <= 1 und 0 <= y0 < y1 <= 1")
        return self


class Step(BaseModel):
    step: int
    phase: Phase
    plates_per_side: int
    added_mass_kg: float


class AnalysisConfig(BaseModel):
    cycles: list[str] = Field(min_length=1)
    max_plates_per_side: int = Field(ge=1)
    plate_mass_kg: float = Field(gt=0)
    collar_mass_kg: float = Field(ge=0)
    geometry: Geometry = Geometry()
    detection: Detection = Detection()
    primary_outcome: Literal["compliance_mm_per_100kg"] = "compliance_mm_per_100kg"
    sign_convention: str = "ends_below_centre_positive"
    alpha: float = Field(default=0.05, gt=0, lt=1)
    seed: int = 0

    def added_mass_kg(self, plates_per_side: int) -> float:
        """Zusatzmasse (Scheiben + Klemmen beider Seiten), ohne Eigengewicht der Stange."""
        if plates_per_side == 0:
            return 0.0
        return 2.0 * (plates_per_side * self.plate_mass_kg + self.collar_mass_kg)

    def schedule(self) -> list[Step]:
        """Stufen eines Zyklus: 0 -> max (up), danach zurück auf 0 (down)."""
        n = self.max_plates_per_side
        plates = list(range(n + 1)) + list(range(n - 1, -1, -1))
        return [
            Step(
                step=i,
                phase="up" if i <= n else "down",
                plates_per_side=p,
                added_mass_kg=self.added_mass_kg(p),
            )
            for i, p in enumerate(plates)
        ]

    @property
    def peak_step(self) -> int:
        return self.max_plates_per_side

    @property
    def final_step(self) -> int:
        return 2 * self.max_plates_per_side


def _load_yaml(path: Path) -> dict:
    with Path(path).open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_bars(path: Path | str = "config/bars.yaml") -> BarCatalog:
    return BarCatalog.model_validate(_load_yaml(Path(path)))


def load_analysis(path: Path | str = "config/analysis.yaml") -> AnalysisConfig:
    return AnalysisConfig.model_validate(_load_yaml(Path(path)))
