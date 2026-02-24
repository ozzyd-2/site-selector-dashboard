"""
Beginner-friendly scoring script for the Site Selector dashboard.

This script:
- loads city-level data from `data/cities.csv` using pandas
- normalizes the numerical columns with simple min–max scaling
- calculates three indices:
  * Cooling Cost Index
  * Water Stress Score
  * Carbon Cost Index
- combines them into a Total Impact Score using the *base-case* weights
- prints a small table showing each city and its scores

Run this file from the project root folder with:

    python logic/scoring.py
"""

from __future__ import annotations

import pandas as pd


# ---------------------------------------------------------------------------
# Helper function: min–max normalization
# ---------------------------------------------------------------------------
def min_max_normalize(series: pd.Series) -> pd.Series:
    """
    Apply simple min–max scaling to a pandas Series.

    Formula (for each value x in the column):
        normalized_x = (x - min_value) / (max_value - min_value)

    This rescales the data so that:
    - the smallest value becomes 0
    - the largest value becomes 1
    - everything else is between 0 and 1
    """
    min_value = series.min()
    max_value = series.max()

    # If the column is constant (all values the same),
    # the denominator would be 0. In that case we just
    # return 0 for every row, because there is no variation.
    if max_value == min_value:
        return pd.Series(0.0, index=series.index)

    return (series - min_value) / (max_value - min_value)


def main() -> None:
    # -----------------------------------------------------------------------
    # 1. Load the data
    # -----------------------------------------------------------------------
    # We assume the CSV file lives in the `data` folder at the project root.
    # IMPORTANT: run this script from the project root so this relative
    # path works:  python logic/scoring.py
    csv_path = "data/cities.csv"

    # Read the CSV into a pandas DataFrame.
    df = pd.read_csv(csv_path)

    # The scoring logic document describes the following input columns.
    # If your CSV uses slightly different names, you can update these
    # variables to match.
    CITY_COL = "City"
    TEMP_COL = "Avg Temp (°F)"
    RAIN_COL = "Avg Monthly Rainfall (in)"
    WATER_PRICE_COL = "Water Price ($/kgal)"
    CARBON_COL = "Grid Carbon Intensity (kg CO₂/kWh)"

    required_columns = [CITY_COL, TEMP_COL, RAIN_COL, WATER_PRICE_COL, CARBON_COL]
    missing = [col for col in required_columns if col not in df.columns]
    if missing:
        raise ValueError(
            f"The following required columns are missing from {csv_path}: {missing}\n"
            "Please check the column names in your CSV file and update them in scoring.py if needed."
        )

    # -----------------------------------------------------------------------
    # 2. Min–max normalize the numerical columns
    # -----------------------------------------------------------------------
    # We create new columns that store the normalized versions. These are
    # the values we will plug into our index formulas.
    df["Temp_norm"] = min_max_normalize(df[TEMP_COL])
    df["Rain_norm"] = min_max_normalize(df[RAIN_COL])
    df["WaterPrice_norm"] = min_max_normalize(df[WATER_PRICE_COL])

    # For rainfall, *more* rain usually means *lower* water stress.
    # The scoring logic uses "Inverse Normalized Avg_Rainfall", which simply
    # means we flip the scale:
    #   high rainfall  -> low stress  -> small number
    #   low rainfall   -> high stress -> large number
    # We can do this by subtracting the normalized value from 1.
    df["Rain_inverse_norm"] = 1 - df["Rain_norm"]

    # -----------------------------------------------------------------------
    # 3. Calculate the three indices
    # -----------------------------------------------------------------------

    # 3.1 Cooling Cost Index (CCI)
    # From scoring_logic.md:
    #   Cooling Cost Index = Normalized Avg_Temp × Cooling Weight
    #
    # Here we set Cooling Weight = 1.0 as a simple base case. You could
    # experiment with other values (e.g., 1.5, 2.0) to emphasize cooling.
    COOLING_WEIGHT = 1.0
    df["Cooling_Cost_Index"] = df["Temp_norm"] * COOLING_WEIGHT

    # 3.2 Water Stress Score (WSS)
    # From scoring_logic.md:
    #   Water Stress Score =
    #       ( Normalized Water_Price × 0.5 ) +
    #       ( Inverse Normalized Avg_Rainfall × 0.5 )
    df["Water_Stress_Score"] = (
        df["WaterPrice_norm"] * 0.5 + df["Rain_inverse_norm"] * 0.5
    )

    # 3.3 Carbon Cost Index (CCI₂)
    # From scoring_logic.md:
    #   Carbon Cost Index = Normalized Avg_Temp × Grid_Carbon
    #
    # Note: the temperature is normalized, but the carbon intensity uses
    # the original units (kg CO₂/kWh). This matches the written formula.
    df["Carbon_Cost_Index"] = df["Temp_norm"] * df[CARBON_COL]

    # -----------------------------------------------------------------------
    # 4. Compute the Total Impact Score for the *base case* scenario
    # -----------------------------------------------------------------------
    # Base Case – Balanced Sustainability:
    #   Total Impact Score =
    #       ( Water Stress Score × 2.0 ) +
    #       ( Carbon Cost Index × 1.5 ) +
    #       ( Cooling Cost Index × 1.0 )
    WATER_WEIGHT_BASE = 2.0
    CARBON_WEIGHT_BASE = 1.5
    COOLING_WEIGHT_BASE = 1.0

    df["Total_Impact_Score"] = (
        df["Water_Stress_Score"] * WATER_WEIGHT_BASE
        + df["Carbon_Cost_Index"] * CARBON_WEIGHT_BASE
        + df["Cooling_Cost_Index"] * COOLING_WEIGHT_BASE
    )

    # -----------------------------------------------------------------------
    # 5. Print a summary table
    # -----------------------------------------------------------------------
    # To make the printed table easy to read, we:
    # - show the city name
    # - show each of the three indices
    # - show the Total Impact Score
    # - sort by Total Impact Score (lowest = more attractive site)

    # Optional: make pandas print fewer decimal places for clarity.
    pd.set_option("display.float_format", "{:.3f}".format)

    score_columns = [
        CITY_COL,
        "Cooling_Cost_Index",
        "Water_Stress_Score",
        "Carbon_Cost_Index",
        "Total_Impact_Score",
    ]

    summary = df[score_columns].sort_values("Total_Impact_Score", ascending=True)

    print("\nSite Selector – Base Case Scores\n")
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
