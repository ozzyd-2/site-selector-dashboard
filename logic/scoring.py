"""
CLI entry point for the site-selector scoring engine.

Computes transparent multi-pillar scores (see ``site_scores.py``) and prints
a summary table. Run from the project root:

    python logic/scoring.py
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from site_scores import DEFAULT_WEIGHTS, score_cities


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    variables_csv = root / "data" / "excel_database(Variables).csv"
    grid_csv = root / "data" / "excel_database(grid_carbon).csv"

    df = score_cities(variables_csv, grid_csv, DEFAULT_WEIGHTS)

    pd.set_option("display.float_format", "{:.3f}".format)

    out_cols = [
        "city",
        "state",
        "Water_Risk_Score",
        "Climate_Load_Index",
        "Carbon_Impact_Score",
        "Energy_Cost_Score",
        "Total_Impact_Score",
    ]
    summary = df[out_cols].sort_values("Total_Impact_Score", ascending=True)

    print("\nWaterRisk Explorers — pillar scores (0–1) and total (0–10, lower is better)\n")
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
