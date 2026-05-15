# Benchmark Instance – Capacity Planning in Remanufacturing

**Case:** 1 Product Variant (CG15) · T = 10 Shifts · S = 10 Stations

## File Overview

| File | Description |
|------|-------------|
| `demand.csv` | Demand D_t per variant per period |
| `cores.csv` | Core availability I_t per variant per period |
| `processes.csv` | All 16 processes with category and stochastic duration |
| `process_chains.csv` | Ordered Prozesskette per variant (primary + fallback) |
| `process_success_prob.csv` | Success probability p_{p,m} per (process, variant) |
| `stations.csv` | Station list with category assignment |
| `compatibility.csv` | bef(s,p) – which process can run on which station |
| `station_capacity_phi.csv` | φ_t – max active stations per period |
| `reconfig_costs.csv` | dow / ass / reco costs and times |
| `reman_share_bounds.csv` | z_{g,v} bounds per variant |
| `parameters_scalar.csv` | Scalar parameters (T, S, M, shift duration) |

---

## Key Design Choices

- **CG15** – current generation, growing demand (avg 15 u/shift)
- Core availability is intentionally **below demand** → forces mix of remanufacturing + linear production
- Shift **t=5**: planned maintenance → φ_t reduced to 6

---

## Process Categories

| Category | Stations | Processes |
|----------|----------|-----------|
| PTran (Transformer) | 1, 2, 3 | p_tran_01 – p_tran_05: disassembly, assembly, screwing, milling/turning, additive processes |
| PInsp (Inspection) | 4, 5, 6 | p_insp_01 – p_insp_05: visual and functional inspection |
| PManu (Manual) | 7, 8, 9, 10 | p_manu_01 – p_manu_06: fallback assembly, disassembly, screwing, drilling |

Each station is assigned to **exactly one** category.

---

## Intralogistics

Station positions and distances are instance-specific and defined externally. The benchmark is layout-agnostic to allow broad applicability across different shopfloor configurations.
