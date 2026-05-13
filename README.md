# Benchmark Instance – Capacity Planning in Remanufacturing

**Case:** 3 Product Variants · T = 20 Shifts · S = 10 Stations

---

## File Overview

| File | Description |
|------|-------------|
| `demand.csv` | Demand D_t per product per period |
| `cores.csv` | Core availability I_t per product per period |
| `processes.csv` | All 16 processes with category and stochastic duration |
| `process_chains.csv` | Ordered Prozesskette per product (primary + fallback) |
| `process_success_prob.csv` | Success probability p_{p,m} per (process, product) |
| `stations.csv` | Station layout, category and grid position |
| `compatibility.csv` | bef(s,p) – which process can run on which station |
| `station_capacity_phi.csv` | φ_t – max active stations per period |
| `reconfig_costs.csv` | dow / ass / reco costs and times |
| `reman_share_bounds.csv` | z_{g,v} bounds per product |
| `parameters_scalar.csv` | Scalar parameters (T, S, M, shift duration, …) |

---

## Key Design Choices

- **CG15** – actual generation, growing demand (avg 15 u/shift),
- **WSG15** – (avg 12 u/shift)
- **WSG14** – phasing out (avg 6 u/shift), lowest success probabilities due to corrosion/wear
- Core availability is intentionally **below demand** → forces mix of remanufacturing + linear production
- Shifts **t=5** and **t=10**: planned maintenance → φ_t reduced to 6
- Station **s=3**: cross-category flexibility (PTran + p_sort_parts)
- Station **s=6**: cross-category flexibility (PInsp + p_test_final)

---

## Process Categories

| Category | Stations | Processes |
|----------|----------|-----------|
| PTran (Transformer) | 1, 2, 3 | disassembly, assembly, screwing, milling turning, additiv processes
| PInsp (Inspection) | 4, 5, 6 | visual
| PManu (Manual) | 7, 8, 9, 10 | fallback for assembly, dissasembly, screwing, drilling |

---

## Intralogistics

Stations are placed on a **5 × 2 grid** with 3 m spacing.  
Manhattan distance: `d(s1,s2) = (|col1−col2| + |row1−row2|) × 3 m`

| s1 | s2 | dist (m) |
|----|----|---------|
| 1 | 2 | 3.0 |
| 1 | 6 | 3.0 |
| 1 | 10 | 15.0 |
| 5 | 10 | 3.0 |
