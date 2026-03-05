"""
City impact scoring script for data center site selection.

This script:
- reads a CSV file with city-level environmental and infrastructure data
- normalizes selected variables using Min–Max normalization
- computes:
  * Water_Risk_Score
  * Cooling_Cost_Index
  * Carbon_Cost
  * Total_Impact_Score
- saves the results to a new CSV file called `city_impact_scores.csv`
- prints the 10 cities with the lowest Total_Impact_Score

You can run it from the project root like:

    python logic/city_impact_scoring.py

Make sure the input CSV path below points to your dataset.
"""

from __future__ import annotations

import os
from typing import Tuple

import pandas as pd


# ---------------------------------------------------------------------------
# Configuration: where to find and save data
# ---------------------------------------------------------------------------

# Path to the input CSV file (relative to the project root).
# Update this if your file has a different name or location.
# The main combined dataset is stored in:
#   data/excel_database(Variables).csv
INPUT_CSV_PATH = "data/excel_database(Variables).csv"

# The output file will be written to the *same folder* as the input CSV.
OUTPUT_CSV_NAME = "city_impact_scores.csv"


# ---------------------------------------------------------------------------
# Helper function: Min–Max normalization
# ---------------------------------------------------------------------------
def min_max_normalize(series: pd.Series) -> pd.Series:
    """
    Apply Min–Max normalization to a pandas Series.

    Formula:
        normalized_value = (value - min_value) / (max_value - min_value)

    This rescales values so that:
    - the minimum becomes 0
    - the maximum becomes 1
    - all other values are between 0 and 1

    If all values in the column are the same, the function returns 0 for
    every row (because there is no variation to scale).
    """
    min_value = series.min()
    max_value = series.max()

    if pd.isna(min_value) or pd.isna(max_value):
        # If the column is entirely NaN, just return NaN.
        return pd.Series([pd.NA] * len(series), index=series.index)

    if max_value == min_value:
        # Avoid dividing by zero when there is no variation.
        return pd.Series(0.0, index=series.index)

    return (series - min_value) / (max_value - min_value)


def clean_currency_column(df: pd.DataFrame, column_name: str) -> None:
    """
    Convert a column with currency-formatted strings (e.g. "$4.95", "$7,767,362,043.20")
    into numeric values that pandas can use for math operations.
    """
    df[column_name] = (
        df[column_name]
        .astype(str)
        .str.replace(r"[\$,]", "", regex=True)
        .str.strip()
    )
    df[column_name] = pd.to_numeric(df[column_name], errors="coerce")


def main() -> None:
    # -----------------------------------------------------------------------
    # Step 1 — Load Data
    # -----------------------------------------------------------------------
    print(f"Loading data from: {INPUT_CSV_PATH}")
    df = pd.read_csv(INPUT_CSV_PATH)

    # For reference, we expect (at minimum) these columns:
    # city, state, state_ID, city_ID, latitude, longitude,
    # avg_Annual_Precipitation, Rain_Jan, ..., Rain_Dec,
    # Avg_Annual_Temp, Avg_Summer_Temp, Cooling_Degree_Days,
    # Heating_Degree_Days, Water_Price, Water_Stress_Index,
    # Drought_Risk, Grid_Carbon_Intensity, Electricity_Price

    # -----------------------------------------------------------------------
    # Step 2 — Normalize Variables
    # -----------------------------------------------------------------------
    # Columns to normalize and their new names.
    columns_to_normalize: Tuple[Tuple[str, str], ...] = (
        ("Water_Stress_Index", "norm_Water_Stress_Index"),
        ("Drought_Risk", "norm_Drought_Risk"),
        ("Water_Price", "norm_Water_Price"),
        ("Avg_Summer_Temp", "norm_Avg_Summer_Temp"),
        ("Grid_Carbon_Intensity", "norm_Grid_Carbon_Intensity"),
        ("Electricity_Price", "norm_Electricity_Price"),
    )

    # The source CSV also contains a second table with data center
    # facility information below the city rows. Those rows do not have
    # values for fields like Avg_Summer_Temp and should be excluded from
    # the city-level scoring.
    df = df[df["Avg_Summer_Temp"].notna()].copy()

    # The Water_Price and Electricity_Price columns are stored as strings
    # with currency formatting (e.g. "$4.95", "$7,767,362,043.20").
    # We first convert them to numeric, then apply min–max normalization.
    clean_currency_column(df, "Water_Price")
    clean_currency_column(df, "Electricity_Price")

    for original_col, norm_col in columns_to_normalize:
        if original_col not in df.columns:
            raise ValueError(
                f"Required column '{original_col}' is missing from the input CSV.\n"
                "Please check your file and column names."
            )
        df[norm_col] = min_max_normalize(df[original_col])

    # -----------------------------------------------------------------------
    # Step 3 — Calculate Water Risk Score
    # -----------------------------------------------------------------------
    # Water_Risk_Score =
    #   (norm_Water_Stress_Index * 2) +
    #   (norm_Drought_Risk * 1.5) +
    #   (norm_Water_Price * 1)
    df["Water_Risk_Score"] = (
        df["norm_Water_Stress_Index"] * 2.0
        + df["norm_Drought_Risk"] * 1.5
        + df["norm_Water_Price"] * 1.0
    )

    # -----------------------------------------------------------------------
    # Step 4 — Calculate Cooling Cost Index
    # -----------------------------------------------------------------------
    # Cooling_Cost_Index =
    #   norm_Avg_Summer_Temp * norm_Electricity_Price
    df["Cooling_Cost_Index"] = (
        df["norm_Avg_Summer_Temp"] * df["norm_Electricity_Price"]
    )

    # -----------------------------------------------------------------------
    # Step 5 — Calculate Carbon Cost
    # -----------------------------------------------------------------------
    # Carbon_Cost =
    #   norm_Grid_Carbon_Intensity * norm_Electricity_Price
    df["Carbon_Cost"] = (
        df["norm_Grid_Carbon_Intensity"] * df["norm_Electricity_Price"]
    )

    # -----------------------------------------------------------------------
    # Step 6 — Calculate Total Impact Score
    # -----------------------------------------------------------------------
    # Total_Impact_Score =
    #   (Water_Risk_Score * 2) +
    #   (Cooling_Cost_Index * 1) +
    #   (Carbon_Cost * 1.5)
    df["Total_Impact_Score"] = (
        df["Water_Risk_Score"] * 2.0
        + df["Cooling_Cost_Index"] * 1.0
        + df["Carbon_Cost"] * 1.5
    )

    # Lower Total_Impact_Score represents a more favorable location.

    # -----------------------------------------------------------------------
    # Step 7 — Output Results
    # -----------------------------------------------------------------------
    # Sort the dataframe by Total_Impact_Score (ascending).
    df_sorted = df.sort_values("Total_Impact_Score", ascending=True)

    # Build output path next to the input CSV.
    input_dir = os.path.dirname(INPUT_CSV_PATH)
    output_path = os.path.join(input_dir or ".", OUTPUT_CSV_NAME)

    # Save the full sorted dataset.
    df_sorted.to_csv(output_path, index=False)
    print(f"Saved impact scores to: {output_path}")

    # Print the top 10 cities with the lowest Total Impact Scores.
    # We show a few key columns for quick inspection.
    print("\nTop 10 cities (lowest Total_Impact_Score):\n")

    # Choose columns to display. Adjust this list if you want more/less detail.
    display_columns = [
        "city",
        "state",
        "Total_Impact_Score",
        "Water_Risk_Score",
        "Cooling_Cost_Index",
        "Carbon_Cost",
    ]

    # Only keep columns that actually exist in the dataframe, to be safe.
    display_columns = [c for c in display_columns if c in df_sorted.columns]

    top_10 = df_sorted.head(10)[display_columns]

    # Format floats to 3 decimal places for readability.
    pd.set_option("display.float_format", "{:.3f}".format)
    print(top_10.to_string(index=False))


if __name__ == "__main__":
    main()

