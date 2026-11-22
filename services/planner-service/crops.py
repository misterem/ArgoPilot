"""FAO-56 crop values used by the planner (single crop coefficient, no climate adjustment).

Sources: FAO Irrigation and Drainage Paper 56, Table 11 (stage lengths), Table 12 (Kc), Table 22 (root depth, p).
See the irrigation-calc-reference skill, "AgroPilot planner method", for why each value was chosen.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Crop:
    id: str
    stages: tuple[int, int, int, int]  # initial, development, mid-season, late (days)
    kc_ini: float
    kc_mid: float
    kc_end: float
    root_depth_m: float  # constant over the season
    p: float  # fraction of the bucket usable before irrigating (constant)

    @property
    def season_length(self) -> int:
        return sum(self.stages)


CROPS: dict[str, Crop] = {
    # Table 11 "Tomato, Mediterranean, April/May" 30/40/45/30. Table 12: Kc ini 0.6 (Solanaceae group row),
    # Kc mid 1.15 (not staked), Kc end 0.80 (middle of 0.70-0.90). Table 22: Zr 0.7 m (smaller end, for
    # scheduling), p 0.40.
    "tomato": Crop("tomato", (30, 40, 45, 30), 0.60, 1.15, 0.80, 0.7, 0.40),
    # Table 11 "Sweet peppers (bell), Europe and Medit." 30/35/40/20 (ini 30 matches the 125-day total).
    # Table 12: Kc ini 0.6 (group row), Kc mid 1.05 (not staked), Kc end 0.90. Table 22: Zr 0.5 m, p 0.30.
    "bell-pepper": Crop("bell-pepper", (30, 35, 40, 20), 0.60, 1.05, 0.90, 0.5, 0.30),
}
