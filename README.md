# Benchmark Instance – Capacity Planning in Remanufacturing

**Case:** 1 Product, G = 2 Generation, V = 1 Variant per generation, T = 10 Shifts · S = 10 Stations
---
## General
The problem is highly abstract, and many values are assumed. This is a simple, illustrative example.
---

## File Overview

| File | Description |
|------|-------------|
| `inpu;cores.csv` | Core availability I_t per variant per period |
| `demand.csv` | Demand D_t per variant per period |
| `parameters_scalar.csv` | Scalar parameters (T, S, M, shift duration) |
| `process_flow_table.csv` | Manufacturing process as flow chart with subsequent processes (The probabilities represent the average transition probability.)|
| `processes.csv` | All 16 processes with category and stochastic duration (exponential) |
| `reconfig_costs.csv` | remproc / addproc / stat costs and times (Purely placeholder costs; no actual machine or tooling costs) |
| `time_lags.csv` | Stochastic durationremproc for time_lags |
---

## Process Categories

| Category | Processes |
|----------|-----------|
| PTran (Transformer) | p_tran_01 – p_tran_05: disassembly, assembly, screwing, milling/turning, additive processes |
| PInsp (Inspection) | p_insp_01 – p_insp_05: visual inspection |
| PManu (Manual) | p_manu_01 – p_manu_06: assembly, disassembly, screwing, drilling |

Each station is assigned to **exactly one** category.

---

## Intralogistics

The stations are arranged in a **5 × 2 grid** with a distance of 3 meters between them. The Manhattan distance formula is used to calculate the distances.
