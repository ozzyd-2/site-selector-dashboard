"""
WaterRisk Explorers — Dashboard JSON Exporter
=============================================
Bridges the Python scoring engine (site_scores.py) to the Lovable frontend.

Produces:  data/dashboard_data.json

Run from the project root:
    python logic/export_dashboard_json.py

The output file is the ONLY thing Lovable needs to know about.
Commit it to GitHub after each scoring run, or serve it as a static file.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from site_scores import (
    DEFAULT_WEIGHTS,
    SCENARIO_WEIGHTS,
    score_cities,
    total_impact_score_row,
)

# ---------------------------------------------------------------------------
# Paths  (adjust if your folder layout differs)
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[1]
VARIABLES_CSV = ROOT / "data" / "excel_database(Variables).csv"
GRID_CSV      = ROOT / "data" / "excel_database(grid_carbon).csv"
OUTPUT_JSON   = ROOT / "data" / "dashboard_data.json"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _safe(val):
    """Convert numpy/pandas scalars to plain Python; NaN → None."""
    if pd.isna(val):
        return None
    try:
        return float(val) if isinstance(val, (float, int)) else val
    except Exception:
        return None


def build_city_record(row: pd.Series, rank: int, weights: dict) -> dict:
    """One city object for the cities[] array."""
    return {
        # Identity
        "rank":      rank,
        "city":      str(row.get("city", "")),
        "state":     str(row.get("state", "")),
        "state_id":  str(row.get("state_ID", row.get("state", ""))),
        "latitude":  _safe(row.get("latitude")),
        "longitude": _safe(row.get("longitude")),

        # Pillar scores  (0–1, higher = worse)
        "scores": {
            "total":        _safe(row.get("Total_Impact_Score")),   # 0–10
            "water_risk":   _safe(row.get("Water_Risk_Score")),
            "climate_load": _safe(row.get("Climate_Load_Index")),
            "carbon":       _safe(row.get("Carbon_Impact_Score")),
            "energy_cost":  _safe(row.get("Energy_Cost_Score")),
        },

        # Raw inputs (useful for tooltips / detail cards in Lovable)
        "inputs": {
            "water_stress_index":      _safe(row.get("Water_Stress_Index")),
            "drought_risk":            _safe(row.get("Drought_Risk")),
            "water_price":             _safe(row.get("Water_Price")),
            "avg_annual_precipitation":_safe(row.get("avg_Annual_Precipitation")),
            "avg_summer_temp":         _safe(row.get("Avg_Summer_Temp")),
            "avg_annual_temp":         _safe(row.get("Avg_Annual_Temp")),
            "cooling_degree_days":     _safe(row.get("Cooling_Degree_Days")),
            "heating_degree_days":     _safe(row.get("Heating_Degree_Days")),
            "grid_carbon_intensity":   _safe(row.get("Grid_Carbon_Intensity")),
            "electricity_price":       _safe(row.get("Electricity_Price")),
        },
    }


def build_scenario_rankings(base_df: pd.DataFrame) -> dict:
    """
    Re-score with each scenario's weights and return ranked city lists.
    Useful for the 'What-If' / scenario comparison panel in Lovable.
    """
    result = {}
    for scenario_name, weights in SCENARIO_WEIGHTS.items():
        scored = base_df.copy()
        scored["Total_Impact_Score"] = scored.apply(
            lambda r: total_impact_score_row(r, weights), axis=1
        )
        ranked = (
            scored[["city", "state", "Total_Impact_Score"]]
            .sort_values("Total_Impact_Score", ascending=True)
            .reset_index(drop=True)
        )
        result[scenario_name] = [
            {
                "rank":  i + 1,
                "city":  str(row["city"]),
                "state": str(row["state"]),
                "total": _safe(row["Total_Impact_Score"]),
            }
            for i, row in ranked.iterrows()
        ]
    return result


# ---------------------------------------------------------------------------
# Main export
# ---------------------------------------------------------------------------
def main() -> None:
    print(f"Loading data …")
    df_base = score_cities(VARIABLES_CSV, GRID_CSV, DEFAULT_WEIGHTS)
    df_sorted = df_base.sort_values("Total_Impact_Score", ascending=True).reset_index(drop=True)

    cities = [
        build_city_record(row, rank=i + 1, weights=DEFAULT_WEIGHTS)
        for i, row in df_sorted.iterrows()
    ]

    scenarios = build_scenario_rankings(df_base)

    # Summary stats (handy for dashboard header cards)
    total_scores = df_sorted["Total_Impact_Score"].dropna()
    summary = {
        "city_count":   len(df_sorted),
        "best_city":    str(df_sorted.iloc[0]["city"]) if len(df_sorted) else None,
        "worst_city":   str(df_sorted.iloc[-1]["city"]) if len(df_sorted) else None,
        "avg_total":    round(float(total_scores.mean()), 3) if not total_scores.empty else None,
        "min_total":    round(float(total_scores.min()), 3) if not total_scores.empty else None,
        "max_total":    round(float(total_scores.max()), 3) if not total_scores.empty else None,
    }

    payload = {
        # ── Meta ──────────────────────────────────────────────────────────
        "meta": {
            "generated_at":      datetime.now(timezone.utc).isoformat(),
            "scoring_version":   "v2",
            "score_direction":   "lower_is_better",
            "total_score_range": "0-10",
            "pillar_score_range": "0-1",
        },

        # ── Default weights used for the main ranking ─────────────────────
        "default_weights": DEFAULT_WEIGHTS,

        # ── Summary KPIs ──────────────────────────────────────────────────
        "summary": summary,

        # ── Per-city records ──────────────────────────────────────────────
        # Lovable: iterate this array to render the leaderboard / map / cards
        "cities": cities,

        # ── Scenario rankings ─────────────────────────────────────────────
        # Lovable: swap between these when the user picks a scenario tab
        "scenarios": scenarios,
    }

    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_JSON, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)

    print(f"\n✅  Exported {len(cities)} cities → {OUTPUT_JSON}")
    print(f"   Best site : {summary['best_city']}  ({summary['min_total']})")
    print(f"   Worst site: {summary['worst_city']}  ({summary['max_total']})")
    print(f"   Avg score : {summary['avg_total']}")
    print(f"\nNext step: commit data/dashboard_data.json to GitHub,")
    print(f"           then point Lovable at the raw URL shown below.")
    print(f"\n   Raw URL pattern (replace <user>/<repo>/<branch>):")
    print(f"   https://raw.githubusercontent.com/<user>/<repo>/<branch>/data/dashboard_data.json")


if __name__ == "__main__":
    main()
