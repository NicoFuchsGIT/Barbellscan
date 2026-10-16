"""Pydantic-Modelle für die YAML-Konfiguration (config/*.yaml)."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, model_validator

Category = Literal["power", "deadlift", "squat"]


class BarModel(BaseModel):
    model_id: str
    name: str
    manufacturer: str
    article: str | None = None
    category: Category
    total_length_mm: float = Field(gt=0)
    shaft_diameter_mm: float = Field(gt=0)
    tensile_strength_psi: float = Field(gt=0)
    shaft_length_mm: float = Field(gt=0)
    weight_kg: float = Field(gt=0)
    replicates: int = Field(default=1, ge=1)

    @model_validator(mode="after")
    def _shaft_shorter_than_bar(self) -> BarModel:
        if self.shaft_length_mm >= self.total_length_mm:
            raise ValueError(f"{self.model_id}: Schaft muss kürzer als die Stange sein")
        return self


class BarCatalog(BaseModel):
    bars: list[BarModel]

    @model_validator(mode="after")
    def _unique_ids(self) -> BarCatalog:
        ids = [b.model_id for b in self.bars]
        if len(ids) != len(set(ids)):
            raise ValueError("model_id muss eindeutig sein")
        return self

    def bar_ids(self) -> list[str]:
        """Physische Stangen: ``<model_id>`` bzw. ``<model_id>_<n>`` bei mehreren Exemplaren."""
        return [
            b.model_id if b.replicates == 1 else f"{b.model_id}_{i}"
            for b in self.bars
            for i in range(1, b.replicates + 1)
        ]

    def model_of(self, bar_id: str) -> BarModel:
        for b in self.bars:
            if bar_id == b.model_id or bar_id.rsplit("_", 1)[0] == b.model_id:
                return b
        raise KeyError(bar_id)


class AnalysisConfig(BaseModel):
    loads_kg: list[float] = Field(min_length=2)
    runs: int = Field(ge=1)
    baseline_after_unload: bool = True
    support_offset_mm: float = Field(gt=0)
    aruco_size_mm: float = Field(default=100.0, gt=0)  # Referenzmarker im Hintergrund
    ball_diameter_mm: float = Field(default=50.0, gt=0)  # gelbe Kugeln an den Kappen
    ball_hang_mm: float = Field(default=0.0, ge=0)  # Kugelmitte unter dem Sleeve-Ende
    primary_definition: Literal["D1", "D2", "D3", "D4"] = "D1"
    sign_convention: str = "ends_below_centre_positive"
    alpha: float = Field(default=0.05, gt=0, lt=1)
    seed: int = 0

    @model_validator(mode="after")
    def _loads_ascending(self) -> AnalysisConfig:
        if self.loads_kg != sorted(set(self.loads_kg)):
            raise ValueError("loads_kg muss streng aufsteigend sein")
        return self

    def images_per_bar_run(self) -> int:
        return len(self.loads_kg) + int(self.baseline_after_unload)


def _load_yaml(path: Path) -> dict:
    with Path(path).open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_bars(path: Path | str = "config/bars.yaml") -> BarCatalog:
    return BarCatalog.model_validate(_load_yaml(Path(path)))


def load_analysis(path: Path | str = "config/analysis.yaml") -> AnalysisConfig:
    return AnalysisConfig.model_validate(_load_yaml(Path(path)))
