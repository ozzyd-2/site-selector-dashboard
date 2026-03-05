"""
Beginner-friendly scoring script for the Site Selector dashboard.

This script:
- loads city-level data from a CSV file using pandas
- normalizes key numerical columns with simple min–max scaling
- calculates four metrics:
  * Water_Risk_Score
  * Cooling_Cost_Index
  * Carbon_Cost
  * Total_Impact_Score
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

    If all values in the column are the same, the function returns 0 for
    every row (because there is no variation to scale).
    """
    min_value = series.min()
    max_value = series.max()

    # If the column is entirely NaN, just return NaN for every row.
    if pd.isna(min_value) or pd.isna(max_value):
        return pd.Series([pd.NA] * len(series), index=series.index)

    # If the column is constant (all values the same),
    # the denominator would be 0. In that case we just
    # return 0 for every row, because there is no variation.
    if max_value == min_value:
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
    # 1. Load the data
    # -----------------------------------------------------------------------
    # We assume the CSV file lives in the `data` folder at the project root.
    # IMPORTANT: run this script from the project root so this relative
    # path works:  python logic/scoring.py
    #
    # The main combined dataset is stored in:
    #   data/excel_database(Variables).csv
    csv_path = "data/excel_database(Variables).csv"

    # Read the CSV into a pandas DataFrame.
    df = pd.read_csv(csv_path)

    # The scoring logic document describes the following input columns.
    # If your CSV uses slightly different names, you can update these
    # variables to match.
    CITY_COL = "city"
    STATE_COL = "state"
    WATER_STRESS_COL = "Water_Stress_Index"
    DROUGHT_RISK_COL = "Drought_Risk"
    WATER_PRICE_COL = "Water_Price"
    SUMMER_TEMP_COL = "Avg_Summer_Temp"
    CARBON_INTENSITY_COL = "Grid_Carbon_Intensity"
    ELECTRICITY_PRICE_COL = "Electricity_Price"

    required_columns = [
        CITY_COL,
        STATE_COL,
        WATER_STRESS_COL,
        DROUGHT_RISK_COL,
        WATER_PRICE_COL,
        SUMMER_TEMP_COL,
        CARBON_INTENSITY_COL,
        ELECTRICITY_PRICE_COL,
    ]
    missing = [col for col in required_columns if col not in df.columns]
    if missing:
        raise ValueError(
            f"The following required columns are missing from {csv_path}: {missing}\n"
            "Please check the column names in your CSV file and update them in scoring.py if needed."
        )

    # The source CSV also contains a second table with data center
    # facility information below the city rows. Those rows do not have
    # values for fields like Avg_Summer_Temp and should be excluded from
    # the city-level scoring.
    df = df[df[SUMMER_TEMP_COL].notna()].copy()

    # -----------------------------------------------------------------------
    # 2. Clean currency fields and normalize the numerical columns
    # -----------------------------------------------------------------------
    # The Water_Price and Electricity_Price columns are stored as strings
    # with currency formatting (e.g. "$4.95", "$7,767,362,043.20").
    # We first convert them to numeric, then apply min–max normalization.
    clean_currency_column(df, WATER_PRICE_COL)
    clean_currency_column(df, ELECTRICITY_PRICE_COL)

    # We create new columns that store the normalized versions. These are
    # the values we will plug into our index formulas.
    df["norm_Water_Stress_Index"] = min_max_normalize(df[WATER_STRESS_COL])
    df["norm_Drought_Risk"] = min_max_normalize(df[DROUGHT_RISK_COL])
    df["norm_Water_Price"] = min_max_normalize(df[WATER_PRICE_COL])
    df["norm_Avg_Summer_Temp"] = min_max_normalize(df[SUMMER_TEMP_COL])
    df["norm_Grid_Carbon_Intensity"] = min_max_normalize(df[CARBON_INTENSITY_COL])
    df["norm_Electricity_Price"] = min_max_normalize(df[ELECTRICITY_PRICE_COL])

    # -----------------------------------------------------------------------
    # 3. Calculate the three component metrics
    # -----------------------------------------------------------------------

    # 3.1 Water Risk Score
    # Water_Risk_Score =
    #   (norm_Water_Stress_Index * 2) +
    #   (norm_Drought_Risk * 1.5) +
    #   (norm_Water_Price * 1)
    df["Water_Risk_Score"] = (
        df["norm_Water_Stress_Index"] * 2.0
        + df["norm_Drought_Risk"] * 1.5
        + df["norm_Water_Price"] * 1.0
    )

    # 3.2 Cooling Cost Index
    # Cooling_Cost_Index =
    #   norm_Avg_Summer_Temp * norm_Electricity_Price
    df["Cooling_Cost_Index"] = (
        df["norm_Avg_Summer_Temp"] * df["norm_Electricity_Price"]
    )

    # 3.3 Carbon Cost
    # Carbon_Cost =
    #   norm_Grid_Carbon_Intensity * norm_Electricity_Price
    df["Carbon_Cost"] = (
        df["norm_Grid_Carbon_Intensity"] * df["norm_Electricity_Price"]
    )

    # -----------------------------------------------------------------------
    # 4. Compute the Total Impact Score
    # -----------------------------------------------------------------------
    # Total_Impact_Score =
    #   (Water_Risk_Score * 2) +
    #   (Cooling_Cost_Index * 1) +
    #   (Carbon_Cost * 1.5)
    WATER_WEIGHT = 2.0
    COOLING_WEIGHT = 1.0
    CARBON_WEIGHT = 1.5

    df["Total_Impact_Score"] = (
        df["Water_Risk_Score"] * WATER_WEIGHT
        + df["Cooling_Cost_Index"] * COOLING_WEIGHT
        + df["Carbon_Cost"] * CARBON_WEIGHT
    )

    # -----------------------------------------------------------------------
    # 5. Print a summary table
    # -----------------------------------------------------------------------
    # To make the printed table easy to read, we:
    # - show the city name
    # - show each of the component indices
    # - show the Total Impact Score
    # - sort by Total Impact Score (lowest = more attractive site)

    # Optional: make pandas print fewer decimal places for clarity.
    pd.set_option("display.float_format", "{:.3f}".format)

    score_columns = [
        CITY_COL,
        STATE_COL,
        "Water_Risk_Score",
        "Cooling_Cost_Index",
        "Carbon_Cost",
        "Total_Impact_Score",
    ]

    summary = df[score_columns].sort_values("Total_Impact_Score", ascending=True)

    print("\nSite Selector – Base Case Scores\n")
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
