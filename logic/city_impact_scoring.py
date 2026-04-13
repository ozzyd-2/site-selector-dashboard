"""
Export scored cities to CSV for the dashboard / downstream tools.

Uses the shared engine in ``site_scores.py`` (multi-pillar, min–max normalized).

Run from the project root:

    python logic/city_impact_scoring.py
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from site_scores import DEFAULT_WEIGHTS, score_cities

INPUT_CSV_PATH = "data/excel_database(Variables).csv"
GRID_CSV_PATH = "data/excel_database(grid_carbon).csv"
OUTPUT_CSV_PATH = "data/city_impact_scores.csv"


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    variables = root / INPUT_CSV_PATH
    grid = root / GRID_CSV_PATH

    print(f"Loading data from: {variables}")
    df = score_cities(variables, grid, DEFAULT_WEIGHTS)

    df_sorted = df.sort_values("Total_Impact_Score", ascending=True)

    output_path = root / OUTPUT_CSV_PATH
    # UTF-8 text CSV: LF line endings, no index column, stable float width, empty cells for NA
    df_sorted.to_csv(
        output_path,
        index=False,
        encoding="utf-8",
        lineterminator="\n",
        na_rep="",
        float_format="%.6f",
    )
    print(f"Saved impact scores to: {output_path}")

    display_columns = [
        "city",
        "state",
        "Total_Impact_Score",
        "Water_Risk_Score",
        "Climate_Load_Index",
        "Carbon_Impact_Score",
        "Energy_Cost_Score",
    ]
    display_columns = [c for c in display_columns if c in df_sorted.columns]

    print("\nTop cities (lowest Total_Impact_Score):\n")
    pd.set_option("display.float_format", "{:.3f}".format)
    print(df_sorted.head(10)[display_columns].to_string(index=False))


if __name__ == "__main__":
    main()
