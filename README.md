# Benchmark Instance – Capacity Planning in Remanufacturing

**Case:** 1 Product, g = 2 Generation, v = 2 Variants · T = 10 Shifts · S = 10 Stations
---

## File Overview

| File | Description |
|------|-------------|
| `cores.csv` | Core availability I_t per variant per period |
| `demand.csv` | Demand D_t per variant per period |
| `parameters_scalar.csv` | Scalar parameters (T, S, M, shift duration) |
| `process_flow_table.csv` | Manufacturing process as flow chart with subsequent processes|
| `processes.csv` | All 16 processes with category and stochastic duration |
| `reconfig_costs.csv` | remproc / addproc / stat costs and times |
| `time_lags.csv` | Stochastic durationremproc for time_lags |
---

## Key Design Choices

- **Generation 2** – current generation, growing demand (avg 15 u/shift)
- Core availability is intentionally **below demand** → forces mix of remanufacturing + linear production
---

## Process Categories

| Category | Stations | Processes |
|----------|----------|-----------|
| PTran (Transformer) | 1, 2, 3 | p_tran_01 – p_tran_05: disassembly, assembly, screwing, milling/turning, additive processes |
| PInsp (Inspection) | 4, 5, 6 | p_insp_01 – p_insp_05: visual inspection |
| PManu (Manual) | 7, 8, 9, 10 | p_manu_01 – p_manu_06: assembly, disassembly, screwing, drilling |

Each station is assigned to **exactly one** category.

---

## Intralogistics

The stations are arranged in a **5 × 2 grid** with a distance of 3 meters between them. The Manhattan distance formula is used to calculate the distances.
