# Scoring Logic – Site Selector Water Risk Dashboard

## Purpose
This document defines how raw city-level data is transformed into
comparative sustainability and risk indicators for site selection.

All outputs are indices intended for relative comparison, not exact costs.

---

## 3.1 Variables Used

| Variable | Source Column | Why It Matters |
|--------|---------------|----------------|
| City | City | Identifier for selection |
| Avg_Temp | Avg Temp (°F) | Higher temperatures increase cooling demand |
| Avg_Rainfall | Avg Monthly Rainfall (in) | Proxy for water availability |
| Water_Price | Water Price ($/kgal) | Economic water risk |
| Grid_Carbon | Grid Carbon Intensity (kg CO₂/kWh) | Environmental impact of energy use |

---

## 3.2 Equations

All metrics are calculated as unitless indices.
Higher values indicate worse performance unless otherwise stated.

### Cooling Cost Index (CCI)

Cooling Cost Index =
Normalized Avg_Temp × Cooling Weight

Rationale:
Higher ambient temperatures increase cooling energy demand
for data center operations.

---

### Water Stress Score (WSS)

Water Stress Score =
( Normalized Water_Price × 0.5 ) +
( Inverse Normalized Avg_Rainfall × 0.5 )

Rationale:
High water prices and low rainfall both indicate greater
water scarcity and operational risk.

---

### Carbon Cost Index (CCI₂)

Carbon Cost Index =
Normalized Avg_Temp × Grid_Carbon

Rationale:
Cooling demand has a higher environmental impact in regions
with carbon-intensive electricity grids.

---

## 3.3 Scenario Logic

### Base Case – Balanced Sustainability

Total Impact Score =
( Water Stress Score × 2.0 ) +
( Carbon Cost Index × 1.5 ) +
( Cooling Cost Index × 1.0 )

---

### Water-Priority Scenario

Total Impact Score =
( Water Stress Score × 3.0 ) +
( Carbon Cost Index × 1.0 ) +
( Cooling Cost Index × 1.0 )

---

### Carbon-Priority Scenario

Total Impact Score =
( Water Stress Score × 1.5 ) +
( Carbon Cost Index × 3.0 ) +
( Cooling Cost Index × 1.0 )


---

## 3.4 Assumptions & Trade-offs

• All indices are normalized to allow fair comparison across cities.
• Weightings represent relative importance, not monetary values.
• Rainfall is used as a proxy for water availability.
• Higher Total Impact Score indicates a less desirable site.

If decision priorities shift, scenario weightings change
while underlying data remains constant.