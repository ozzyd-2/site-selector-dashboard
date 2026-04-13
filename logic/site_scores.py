"""
Transparent multi-pillar scoring for the site-selector dashboard.

All raw inputs are min–max normalized to [0, 1] across the scored city rows
(higher = worse for “higher is bad” variables; lower precipitation uses an
inverted normalization so drier = higher risk).

Primary indices (each in [0, 1]):
  - Water_Risk_Score
  - Climate_Load_Index  (cooling / thermal load proxy)
  - Carbon_Impact_Score
  - Energy_Cost_Score   (infrastructure / energy cost proxy)

Total_Impact_Score (0–10 scale) =
  10 * weighted_mean(pillars | user weights)

Lower Total_Impact_Score = better site.

Optional enrichment from ``data/excel_database(grid_carbon).csv`` adds
state-level CO2 (MMT), grid MWh, and industrial total price when parsing
succeeds; otherwise those terms are omitted.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

# ---------------------------------------------------------------------------
# Default user-facing weights (dashboard sliders / scenarios)
# ---------------------------------------------------------------------------
DEFAULT_WEIGHTS: Dict[str, float] = {
    "water": 2.0,
    "climate": 1.0,
    "carbon": 1.5,
    "cost": 2.0,
}

SCENARIO_WEIGHTS: Dict[str, Dict[str, float]] = {
    "balanced": {"water": 2.0, "climate": 1.0, "carbon": 1.5, "cost": 2.0},
    "carbon_priority": {"water": 1.5, "climate": 1.0, "carbon": 3.0, "cost": 1.0},
    "cost_priority": {"water": 1.0, "climate": 2.0, "carbon": 1.0, "cost": 3.0},
    "water_priority": {"water": 3.0, "climate": 1.0, "carbon": 1.0, "cost": 1.0},
}

RAIN_MONTH_COLS: List[str] = [
    "Rain_Jan",
    "Rain_Feb",
    "Rain_Mar",
    "Rain_Apr",
    "Rain_May",
    "Rain_Jun",
    "Rain_Jul",
    "Rain_Aug",
    "Rain_Sep",
    "Rain_Oct",
    "Rain_Nov",
    "Rain_Dec",
]


def min_max_normalize(series: pd.Series) -> pd.Series:
    min_value = series.min()
    max_value = series.max()
    if pd.isna(min_value) or pd.isna(max_value):
        return pd.Series([pd.NA] * len(series), index=series.index)
    if max_value == min_value:
        return pd.Series(0.0, index=series.index)
    return (series - min_value) / (max_value - min_value)


def clean_currency_column(df: pd.DataFrame, column_name: str) -> None:
    df[column_name] = (
        df[column_name]
        .astype(str)
        .str.replace(r"[\$,]", "", regex=True)
        .str.strip()
    )
    df[column_name] = pd.to_numeric(df[column_name], errors="coerce")


def _parse_number_loose(x: object) -> Optional[float]:
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return None
    s = str(x).strip()
    if not s or s.lower() == "nan":
        return None
    s = re.sub(r"[\$,]", "", s)
    try:
        return float(s)
    except ValueError:
        return None


def load_grid_carbon_enrichment(
    grid_path: Path,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Returns (city_enrichment, state_industrial_price) or empty frames.

    city_enrichment columns: city, CO2_million_metric_tons, Grid_MWh
    state_industrial_price columns: state_ID, Industrial_Total_USD
    """
    city_rows: List[dict] = []
    state_prices: List[dict] = []

    if not grid_path.is_file():
        return pd.DataFrame(), pd.DataFrame()

    raw = pd.read_csv(grid_path, header=None, dtype=str)
    # City block: first row whose column 1 is exactly "City"
    header_idx: Optional[int] = None
    for i in range(min(15, len(raw))):
        cell = raw.iloc[i, 1]
        if isinstance(cell, str) and cell.strip() == "City":
            header_idx = i
            break
    if header_idx is not None:
        j = header_idx + 1
        while j < len(raw) and j < header_idx + 12:
            city = raw.iloc[j, 1]
            if not isinstance(city, str) or not city.strip():
                j += 1
                continue
            if city.strip() == "City":
                break
            co2 = _parse_number_loose(raw.iloc[j, 4])
            mwh = _parse_number_loose(raw.iloc[j, 5])
            if co2 is not None or mwh is not None:
                city_rows.append(
                    {
                        "city": city.strip(),
                        "CO2_million_metric_tons": co2,
                        "Grid_MWh": mwh,
                    }
                )
            j += 1

    # Industrial total price block: rows like VA,1,"91,059,344","$7,767,..."
    for i in range(len(raw)):
        sid = raw.iloc[i, 0]
        if isinstance(sid, str) and len(sid.strip()) == 2 and sid.strip().isalpha():
            price = _parse_number_loose(raw.iloc[i, 3])
            if price is not None and price > 0:
                state_prices.append(
                    {"state_ID": sid.strip().upper(), "Industrial_Total_USD": price}
                )

    city_df = pd.DataFrame(city_rows)
    price_df = pd.DataFrame(state_prices)
    if not price_df.empty:
        price_df = price_df.drop_duplicates(subset=["state_ID"], keep="first")
    return city_df, price_df


def load_city_table(variables_csv: Path) -> pd.DataFrame:
    df = pd.read_csv(variables_csv)
    if "Avg_Summer_Temp" not in df.columns:
        raise ValueError("Expected column Avg_Summer_Temp in variables CSV.")
    df = df[df["Avg_Summer_Temp"].notna()].copy()
    return df


def attach_enrichment(df: pd.DataFrame, grid_path: Path) -> pd.DataFrame:
    city_enr, state_prices = load_grid_carbon_enrichment(grid_path)
    if city_enr.empty:
        df["CO2_million_metric_tons"] = pd.NA
        df["Grid_MWh"] = pd.NA
    else:
        df = df.merge(city_enr, on="city", how="left")
    if state_prices.empty or "state_ID" not in df.columns:
        df["Industrial_Total_USD"] = pd.NA
    else:
        df = df.merge(state_prices, on="state_ID", how="left")
    return df


def compute_pillar_scores(df: pd.DataFrame) -> pd.DataFrame:
    """
    Mutates df with norm_* columns and pillar scores.
    """
    work = df.copy()

    clean_currency_column(work, "Water_Price")
    clean_currency_column(work, "Electricity_Price")

    # --- Normalized drivers (0 = best, 1 = worst within cohort) ---
    work["norm_Water_Stress_Index"] = min_max_normalize(
        pd.to_numeric(work["Water_Stress_Index"], errors="coerce")
    )
    work["norm_Drought_Risk"] = min_max_normalize(
        pd.to_numeric(work["Drought_Risk"], errors="coerce")
    )
    work["norm_Water_Price"] = min_max_normalize(work["Water_Price"])

    precip = pd.to_numeric(work["avg_Annual_Precipitation"], errors="coerce")
    work["norm_precip_dryness"] = 1.0 - min_max_normalize(precip)

    # Monthly rainfall variability (seasonality / uneven water supply)
    present_rain = [c for c in RAIN_MONTH_COLS if c in work.columns]
    if len(present_rain) >= 2:
        rain_vals = work[present_rain].apply(pd.to_numeric, errors="coerce")
        work["rain_monthly_std"] = rain_vals.std(axis=1)
        work["norm_rain_variability"] = min_max_normalize(work["rain_monthly_std"])
    else:
        work["norm_rain_variability"] = 0.0

    work["norm_Avg_Summer_Temp"] = min_max_normalize(
        pd.to_numeric(work["Avg_Summer_Temp"], errors="coerce")
    )
    work["norm_Avg_Annual_Temp"] = min_max_normalize(
        pd.to_numeric(work["Avg_Annual_Temp"], errors="coerce")
    )
    work["norm_CDD"] = min_max_normalize(
        pd.to_numeric(work["Cooling_Degree_Days"], errors="coerce")
    )
    work["norm_HDD"] = min_max_normalize(
        pd.to_numeric(work["Heating_Degree_Days"], errors="coerce")
    )

    work["norm_Grid_Carbon_Intensity"] = min_max_normalize(
        pd.to_numeric(work["Grid_Carbon_Intensity"], errors="coerce")
    )

    co2 = pd.to_numeric(work.get("CO2_million_metric_tons"), errors="coerce")
    if co2.notna().any():
        work["norm_CO2_million_tons"] = min_max_normalize(co2)
    else:
        work["norm_CO2_million_tons"] = pd.NA

    mwh = pd.to_numeric(work.get("Grid_MWh"), errors="coerce")
    if mwh.notna().any():
        work["norm_Grid_MWh"] = min_max_normalize(mwh)
    else:
        work["norm_Grid_MWh"] = pd.NA

    work["norm_Electricity_Price"] = min_max_normalize(work["Electricity_Price"])
    ind = pd.to_numeric(work.get("Industrial_Total_USD"), errors="coerce")
    if ind.notna().any():
        work["norm_Industrial_Total_USD"] = min_max_normalize(ind)
    else:
        work["norm_Industrial_Total_USD"] = pd.NA

    # --- Pillars (transparent fixed inner weights) ---
    work["Water_Risk_Score"] = (
        0.34 * work["norm_Water_Stress_Index"]
        + 0.28 * work["norm_Drought_Risk"]
        + 0.22 * work["norm_Water_Price"]
        + 0.11 * work["norm_precip_dryness"]
        + 0.05 * work["norm_rain_variability"]
    )

    work["Climate_Load_Index"] = (
        0.34 * work["norm_Avg_Summer_Temp"]
        + 0.30 * work["norm_CDD"]
        + 0.18 * work["norm_Avg_Annual_Temp"]
        + 0.18 * work["norm_HDD"]
    )

    carbon_cols = [work["norm_Grid_Carbon_Intensity"]]
    if work["norm_CO2_million_tons"].notna().any():
        carbon_cols.append(work["norm_CO2_million_tons"])
    if work["norm_Grid_MWh"].notna().any():
        carbon_cols.append(work["norm_Grid_MWh"])
    work["Carbon_Impact_Score"] = pd.concat(carbon_cols, axis=1).mean(axis=1, skipna=True)

    cost_a = work["norm_Electricity_Price"]
    if work["norm_Industrial_Total_USD"].notna().any():
        cost_b = work["norm_Industrial_Total_USD"].fillna(cost_a)
        work["Energy_Cost_Score"] = 0.5 * cost_a + 0.5 * cost_b
    else:
        work["Energy_Cost_Score"] = cost_a

    return work


def total_impact_score_row(
    row: pd.Series,
    weights: Optional[Dict[str, float]] = None,
) -> float:
    w = {**DEFAULT_WEIGHTS, **(weights or {})}
    pairs = [
        (row.get("Water_Risk_Score"), w["water"]),
        (row.get("Climate_Load_Index"), w["climate"]),
        (row.get("Carbon_Impact_Score"), w["carbon"]),
        (row.get("Energy_Cost_Score"), w["cost"]),
    ]
    num = 0.0
    den = 0.0
    for val, ww in pairs:
        if ww > 0 and pd.notna(val):
            num += float(val) * ww
            den += ww
    if den <= 0:
        return float("nan")
    return round(10.0 * num / den, 3)


def score_cities(
    variables_csv: str | Path,
    grid_carbon_csv: Optional[str | Path] = None,
    weights: Optional[Dict[str, float]] = None,
) -> pd.DataFrame:
    variables_csv = Path(variables_csv)
    df = load_city_table(variables_csv)
    grid_path = Path(grid_carbon_csv) if grid_carbon_csv else variables_csv.parent / "excel_database(grid_carbon).csv"
    df = attach_enrichment(df, grid_path)
    df = compute_pillar_scores(df)
    w = {**DEFAULT_WEIGHTS, **(weights or {})}

    df["Total_Impact_Score"] = df.apply(
        lambda r: total_impact_score_row(r, w), axis=1
    )
    return df
