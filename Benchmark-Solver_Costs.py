import os
for _v in (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
):
    os.environ[_v] = "1"
import argparse
import math
import random
import re
import statistics
from multiprocessing import Pool
from pathlib import Path
import pandas as pd
import pulp

# ======================================================================
# 0. KONFIGURATION
# ======================================================================
DEFAULT_DATA_DIR = os.environ.get(
    "BENCH_DATA_DIR",
    str(Path(__file__).resolve().parent),
)

START_STEP = "Inspection 1"
MAX_PATHLEN = 20
GAP_REL = 0.02

# True: Rest-Wahrscheinlichkeit führt zum Ausschleusen des Cores.
# False: SHARE-Werte werden auf 1 normalisiert.
REMAINDER_IS_REJECTION = True

# True: Bearbeitungsdauer je Schritt wird exponentialverteilt gezogen.
# False: Es werden nur die Mittelwerte verwendet.
STOCHASTIC_DURATIONS = True

# True: Add-/Remove-Kosten sind prozessspezifisch.
# False: Für alle Prozesse werden Durchschnittskosten verwendet.
PROCESS_SPECIFIC_COSTS = True

CATS = ["Tran", "Insp", "Manu", "Empty"]
WORK_CATS = ["Tran", "Insp", "Manu"]


# ======================================================================
# 1. DATEN LADEN
# ======================================================================
def load_data(data_dir):
    d = Path(data_dir)

    processes = pd.read_csv(d / "processes.csv")
    demand_df = pd.read_csv(d / "demand.csv")
    cores_df = pd.read_csv(d / "input_cores.csv")
    scalars_df = pd.read_csv(d / "parameters_scalar.csv")
    stat_df = pd.read_csv(d / "reconfig_costs_stat.csv", index_col=0)
    addpro_df = pd.read_csv(d / "reconfig_costs_addpro.csv", index_col=0)
    rempro_df = pd.read_csv(d / "reconfig_costs_rempro.csv", index_col=0)

    flow = pd.read_csv(
        d / "process_flow.csv",
        sep=";",
        encoding="utf-8-sig",
    ).dropna(how="all")

    flow["FROM_STEP"] = flow["FROM_STEP"].astype(str).str.strip()
    flow["TO_STEP"] = flow["TO_STEP"].astype(str).str.strip()
    flow["SHARE"] = flow["SHARE"].astype(float)

    flow = flow[
        (flow["FROM_STEP"] != "")
        & (flow["TO_STEP"] != "")
        & (flow["FROM_STEP"] != "nan")
        & (flow["TO_STEP"] != "nan")
    ]

    transitions = {}
    for r in flow.itertuples(index=False):
        transitions.setdefault(r.FROM_STEP, []).append(
            (r.TO_STEP, r.SHARE)
        )

    sc = dict(zip(scalars_df["parameter"], scalars_df["value"]))

    name_map = {
        "Manual": "Manu",
        "Inspection": "Insp",
        "Transformer cell": "Tran",
        "Empty": "Empty",
    }

    c_stat = {
        (name_map[r], name_map[c]): float(stat_df.loc[r, c])
        for r in stat_df.index
        for c in stat_df.columns
    }

    c_add = float(
        pd.to_numeric(addpro_df.stack(), errors="coerce").mean()
    )
    c_rem = float(
        pd.to_numeric(rempro_df.stack(), errors="coerce").mean()
    )

    pids = processes["category"].tolist()
    add_p, rem_p = process_costs(
        addpro_df,
        rempro_df,
        pids,
        c_add,
        c_rem,
    )

    return {
        "processes": processes,
        "demand": {
            int(r.period): float(r.demand)
            for r in demand_df.itertuples()
        },
        "cores": {
            int(r.period): float(r.cores_available)
            for r in cores_df.itertuples()
        },
        "transitions": transitions,
        "T": int(sc["T"]),
        "S_MAX": int(sc["Smax"]),
        "M_PROC": int(sc["M"]),
        "SHIFT": float(sc["shift_duration"]),
        "c_stat": c_stat,
        "c_add": c_add,
        "c_rem": c_rem,
        "add_p": add_p,
        "rem_p": rem_p,
    }


def label_to_process(label):
    """Ordnet ein Label aus den Kostenmatrizen einem Prozess zu."""
    n = str(label).strip().lower()
    manual = "manual" in n or "manuell" in n

    if n.startswith("empty") or n.startswith("unnamed") or n in ("nan", ""):
        return None
    if "additiv" in n:
        return "p_tran_02"
    if "turning" in n:
        return "p_tran_05"
    if "thermo" in n:
        return "p_manu_03"
    if "drilling" in n:
        return "p_manu_04"
    if "milling" in n:
        return "p_manu_05" if manual else "p_tran_03"
    if n.startswith("dis") or n.startswith("dia"):
        return "p_manu_02" if manual else "p_tran_04"
    if n.startswith("ass"):
        return "p_manu_01" if manual else "p_tran_01"

    return None


def process_costs(addpro_df, rempro_df, pids, c_add_avg, c_rem_avg):
    """
    Add-Kosten je Prozess: Mittel der passenden Spalten.
    Remove-Kosten je Prozess: Mittel der passenden Zeilen.

    Nullwerte und leere Zellen werden ignoriert.
    Prozesse ohne Eintrag erhalten den Mittelwert der übrigen Prozesse.
    """

    def pos_mean(df):
        values = pd.to_numeric(
            pd.Series(df.to_numpy().ravel()),
            errors="coerce",
        ).dropna()

        values = values[values > 0]
        return float(values.mean()) if len(values) else None

    add_costs = {}
    rem_costs = {}

    for p in pids:
        cols = [
            c for c in addpro_df.columns
            if label_to_process(c) == p
        ]
        rows = [
            r for r in rempro_df.index
            if label_to_process(r) == p
        ]

        add_costs[p] = (
            pos_mean(addpro_df[cols]) if cols else None
        )
        rem_costs[p] = (
            pos_mean(rempro_df.loc[rows]) if rows else None
        )

    known_add = [
        v for v in add_costs.values()
        if v is not None
    ]
    known_rem = [
        v for v in rem_costs.values()
        if v is not None
    ]

    fallback_add = (
        sum(known_add) / len(known_add)
        if known_add
        else c_add_avg
    )
    fallback_rem = (
        sum(known_rem) / len(known_rem)
        if known_rem
        else c_rem_avg
    )

    add_costs = {
        p: (v if v is not None else fallback_add)
        for p, v in add_costs.items()
    }
    rem_costs = {
        p: (v if v is not None else fallback_rem)
        for p, v in rem_costs.items()
    }

    return add_costs, rem_costs


# ======================================================================
# 2. PROZESSSCHRITT -> PROZESS UND KATEGORIE
# ======================================================================
def step_to_process(step):
    """Ordnet einen Prozessschritt einem Prozess aus processes.csv zu."""
    n = step.lower()
    m = re.match(r"inspection\s*(\d)", n)

    if m:
        return f"p_insp_0{m.group(1)}"

    if "(manual)" in n:
        if "disassembly" in n:
            return "p_manu_02"
        if "assembly" in n:
            return "p_manu_01"
        if "thermo" in n:
            return "p_manu_03"
        if "drilling" in n:
            return "p_manu_04"
        if "milling" in n:
            return "p_manu_05"
    else:
        if "disassembly" in n:
            return "p_tran_04"
        if "assembly" in n:
            return "p_tran_01"
        if "additiv" in n:
            return "p_tran_02"
        if "milling" in n:
            return "p_tran_03"
        if "turning" in n:
            return "p_tran_05"

    raise ValueError(
        f"Prozessschritt '{step}' kann keinem Prozess zugeordnet werden"
    )


def proc_category(p):
    if "tran" in p:
        return "Tran"
    if "insp" in p:
        return "Insp"
    return "Manu"


# ======================================================================
# 3. STOCHASTISCHER BEDARF JE PROZESS
# ======================================================================
def sample_path(transitions, start=START_STEP, max_len=MAX_PATHLEN):
    path = [start]
    current = start

    for _ in range(max_len - 1):
        options = transitions.get(current)

        if not options:
            break

        tos, probs = zip(*options)
        total = sum(probs)

        if total <= 0:
            break

        if REMAINDER_IS_REJECTION and random.random() >= total:
            break

        current = random.choices(tos, weights=probs, k=1)[0]
        path.append(current)

    return path


def draw_need(D, n_scen):
    """
    need[t][p] = erwartete Bearbeitungsminuten von Prozess p je Core
    in Periode t, geschätzt über n_scen gesampelte Pfade.
    """
    durations = dict(
        zip(
            D["processes"]["category"],
            D["processes"]["duration_mean_min"],
        )
    )

    need = {}

    for t in range(1, D["T"] + 1):
        acc = {p: 0.0 for p in durations}

        for _ in range(n_scen):
            for step in sample_path(D["transitions"]):
                p = step_to_process(step)

                if STOCHASTIC_DURATIONS:
                    acc[p] += random.expovariate(1.0 / durations[p])
                else:
                    acc[p] += durations[p]

        need[t] = {
            p: acc[p] / n_scen
            for p in durations
        }

    return need


# ======================================================================
# 4. EXPERIMENT
# ======================================================================
def make_solver(time_limit):
    """Wählt CBC, falls verfügbar, sonst HiGHS. Pro Solver ein Thread."""
    if pulp.PULP_CBC_CMD().available():
        return pulp.PULP_CBC_CMD(
            msg=False,
            timeLimit=time_limit,
            gapRel=GAP_REL,
            threads=1,
        )

    return pulp.HiGHS(
        msg=False,
        timeLimit=time_limit,
        gapRel=GAP_REL,
        threads=1,
    )


def max_reman(D, need_t, cap):
    """
    Größte Menge (<= cap), die in einer Periode mit S_MAX Stationen
    bearbeitbar ist.
    """
    S = D["S_MAX"]
    shift = D["SHIFT"]
    m_proc = D["M_PROC"]

    mins = {}
    kmin = {}

    for category in WORK_CATS:
        processes = [
            p for p in need_t
            if proc_category(p) == category and need_t[p] > 1e-12
        ]

        mins[category] = sum(need_t[p] for p in processes)
        kmin[category] = math.ceil(len(processes) / m_proc)

    best = 0.0

    for k_tran in range(kmin["Tran"], S + 1):
        for k_insp in range(kmin["Insp"], S - k_tran + 1):
            k_manu = S - k_tran - k_insp

            if k_manu < kmin["Manu"]:
                continue

            r = cap

            for category, k in (
                ("Tran", k_tran),
                ("Insp", k_insp),
                ("Manu", k_manu),
            ):
                if mins[category] > 0:
                    r = min(
                        r,
                        k * shift / mins[category],
                    )

            best = max(best, r)

    return cap if best >= cap else best * (1 - 1e-6)


def run_one(D, objective, n_scen, time_limit, seed):
    random.seed(seed)

    periods = list(range(1, D["T"] + 1))
    stations = list(range(1, D["S_MAX"] + 1))
    proc_ids = D["processes"]["category"].tolist()

    pcat = {
        p: proc_category(p)
        for p in proc_ids
    }

    shift = D["SHIFT"]
    m_proc = D["M_PROC"]
    demand = D["demand"]
    cores = D["cores"]

    reman_cap = {
        t: min(demand[t], cores[t])
        for t in periods
    }

    need = draw_need(D, n_scen)

    r_max = {
        t: max_reman(D, need[t], reman_cap[t])
        for t in periods
    }

    prob = pulp.LpProblem(
        "Remanufacturing",
        pulp.LpMaximize if objective == "share" else pulp.LpMinimize,
    )

    w = pulp.LpVariable.dicts(
        "w",
        (stations, CATS, periods),
        cat="Binary",
    )
    u = pulp.LpVariable.dicts(
        "u",
        (stations, proc_ids, periods),
        cat="Binary",
    )
    y = pulp.LpVariable.dicts(
        "y",
        (stations, proc_ids, periods),
        lowBound=0,
    )
    reman = pulp.LpVariable.dicts(
        "reman",
        periods,
        lowBound=0,
    )

    trans = [0] + periods[:-1]

    zz = pulp.LpVariable.dicts(
        "zz",
        (stations, CATS, CATS, trans),
        lowBound=0,
        upBound=1,
    )
    add = pulp.LpVariable.dicts(
        "add",
        (stations, proc_ids, trans),
        lowBound=0,
    )
    rem = pulp.LpVariable.dicts(
        "rem",
        (stations, proc_ids, trans),
        lowBound=0,
    )

    def w_at(s, category, t):
        if t == 0:
            return 1 if category == "Empty" else 0
        return w[s][category][t]

    def u_at(s, p, t):
        if t == 0:
            return 0
        return u[s][p][t]

    # --- Stationen ----------------------------------------------------
    for s in stations:
        for t in periods:
            prob += pulp.lpSum(
                w[s][category][t]
                for category in CATS
            ) == 1

            prob += pulp.lpSum(
                u[s][p][t]
                for p in proc_ids
            ) <= m_proc

            prob += pulp.lpSum(
                y[s][p][t]
                for p in proc_ids
            ) <= shift * (1 - w[s]["Empty"][t])

            for p in proc_ids:
                prob += u[s][p][t] <= w[s][pcat[p]][t]
                prob += y[s][p][t] <= shift * u[s][p][t]

    # --- Menge und Arbeitsbedarf --------------------------------------
    for t in periods:
        if objective == "share":
            prob += reman[t] <= reman_cap[t]
        else:
            prob += reman[t] == r_max[t]

        for p in proc_ids:
            prob += pulp.lpSum(
                y[s][p][t]
                for s in stations
            ) == reman[t] * need[t][p]

    # --- Rekonfiguration ----------------------------------------------
    for t in trans:
        for s in stations:
            for k in CATS:
                for k2 in CATS:
                    prob += zz[s][k][k2][t] <= w_at(s, k, t)
                    prob += zz[s][k][k2][t] <= w_at(s, k2, t + 1)
                    prob += (
                        zz[s][k][k2][t]
                        >= w_at(s, k, t) + w_at(s, k2, t + 1) - 1
                    )

            prob += pulp.lpSum(
                zz[s][k][k2][t]
                for k in CATS
                for k2 in CATS
            ) == 1

            for p in proc_ids:
                prob += (
                    add[s][p][t] - rem[s][p][t]
                    == u_at(s, p, t + 1) - u_at(s, p, t)
                )

    if PROCESS_SPECIFIC_COSTS:
        c_add = D["add_p"]
        c_rem = D["rem_p"]
    else:
        c_add = {
            p: D["c_add"]
            for p in proc_ids
        }
        c_rem = {
            p: D["c_rem"]
            for p in proc_ids
        }

    reconfig_cost = (
        pulp.lpSum(
            D["c_stat"][(k, k2)] * zz[s][k][k2][t]
            for s in stations
            for k in CATS
            for k2 in CATS
            for t in trans
        )
        + pulp.lpSum(
            c_add[p] * add[s][p][t]
            + c_rem[p] * rem[s][p][t]
            for s in stations
            for p in proc_ids
            for t in trans
        )
    )

    idle_expr = pulp.lpSum(
        shift * (1 - w[s]["Empty"][t])
        - pulp.lpSum(y[s][p][t] for p in proc_ids)
        for s in stations
        for t in periods
    )

    if objective == "idle":
        prob += idle_expr
    elif objective == "share":
        prob += pulp.lpSum(reman[t] for t in periods)
    else:
        prob += reconfig_cost

    prob.solve(make_solver(time_limit))

    # Nur gültige Lösungen auswerten.
    if (
        prob.sol_status
        not in (
            pulp.LpSolutionOptimal,
            pulp.LpSolutionIntegerFeasible,
        )
        or pulp.value(prob.objective) is None
    ):
        print(
            f"seed={seed}: status={pulp.LpStatus[prob.status]} "
            f"sol_status={prob.sol_status}",
            flush=True,
        )
        return None

    per = {}

    for t in periods:
        active = sum(
            1
            for s in stations
            if (pulp.value(w[s]["Empty"][t]) or 0) < 0.5
        )
        avail = active * shift

        used = sum(
            pulp.value(y[s][p][t]) or 0
            for s in stations
            for p in proc_ids
        )

        ru = pulp.value(reman[t]) or 0

        per[t] = {
            "active": active,
            "avail": avail,
            "used": used,
            "idle": avail - used,
            "util": used / avail * 100 if avail > 0 else 0.0,
            "z": ru / demand[t] if demand[t] > 0 else 0.0,
            "reman": ru,
        }

    return {
        "cost": pulp.value(reconfig_cost),
        "idle": pulp.value(idle_expr),
        "reman": sum(v["reman"] for v in per.values()),
        "min_per_core": sum(need[1].values()),
        "per": per,
    }


# ======================================================================
# 5. PARALLELE LÄUFE
# ======================================================================
_D = None


def _init_worker(D):
    """Lädt die Daten einmal pro Worker-Prozess."""
    global _D
    _D = D


def _worker(args):
    objective, n_scen, time_limit, seed = args
    return run_one(
        _D,
        objective,
        n_scen,
        time_limit,
        seed,
    )


# ======================================================================
# 6. MEHRFACH-LÄUFE UND AUSGABE
# ======================================================================
def main(objective):
    ap = argparse.ArgumentParser()

    ap.add_argument("--runs", type=int, default=25)
    ap.add_argument(
        "--scen",
        type=int,
        default=20,
        help="Anzahl gesampelter Pfade je Periode",
    )
    ap.add_argument(
        "--time-limit",
        type=int,
        default=10000,
        help="Zeitlimit in Sekunden pro Lauf",
    )
    ap.add_argument("--data-dir", default=DEFAULT_DATA_DIR)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument(
        "--workers",
        type=int,
        default=6,
        help="Anzahl paralleler Worker",
    )

    a = ap.parse_args()

    if a.runs < 1:
        ap.error("--runs muss mindestens 1 sein")
    if a.workers < 1:
        ap.error("--workers muss mindestens 1 sein")

    D = load_data(a.data_dir)
    periods = list(range(1, D["T"] + 1))
    workers = min(a.workers, a.runs)

    print(
        f"Objective: {objective} | "
        f"S={D['S_MAX']} M={D['M_PROC']} T={D['T']} "
        f"shift={D['SHIFT']:.0f} min | "
        f"C_add={D['c_add']:,.1f} C_rem={D['c_rem']:,.1f}"
    )
    print(
        f"Worker: {workers} | Läufe: {a.runs} | "
        f"Szenarien je Periode: {a.scen} | "
        f"Zeitlimit je Lauf: {a.time_limit}s"
    )

    jobs = [
        (objective, a.scen, a.time_limit, a.seed + r)
        for r in range(a.runs)
    ]

    res = []

    with Pool(
        processes=workers,
        initializer=_init_worker,
        initargs=(D,),
    ) as pool:
        for completed, out in enumerate(
            pool.imap_unordered(_worker, jobs),
            start=1,
        ):
            if out is None:
                print(
                    f"Fortschritt {completed}/{a.runs}: "
                    "kein gültiges Ergebnis",
                    flush=True,
                )
            else:
                res.append(out)

                if (
                    completed == 1
                    or completed % 50 == 0
                    or completed == a.runs
                ):
                    print(
                        f"Fortschritt {completed}/{a.runs}: "
                        f"zuletzt cost={out['cost']:,.1f} "
                        f"idle={out['idle']:,.1f} "
                        f"reman={out['reman']:,.1f}",
                        flush=True,
                    )

    if not res:
        raise RuntimeError("Kein Lauf war lösbar.")

    m = statistics.mean

    print(
        f"\n=========== ERGEBNISSE "
        f"({len(res)}/{a.runs} gültige Läufe) ==========="
    )
    print(
        "Erwartete Minuten je Core (Periode 1): "
        f"{m(r['min_per_core'] for r in res):.2f}"
    )
    print(
        "Avg total reman units:         "
        f"{m(r['reman'] for r in res):,.1f}"
    )
    print(
        "Avg reconfiguration cost:      "
        f"{m(r['cost'] for r in res):,.2f}"
    )
    print(
        "Avg idle time:                 "
        f"{m(r['idle'] for r in res):,.1f} min"
    )
    print(
        "Avg reman share z_t:           "
        f"{m(m(v['z'] for v in r['per'].values()) for r in res):.4f}"
    )
    print(
        "Avg station utilisation:       "
        f"{m(m(v['util'] for v in r['per'].values()) for r in res):.2f} %"
    )

    print(
        "\nPeriod | Demand |  z_t  | Active | Avail.min "
        "| Used min | Idle min | Util %"
    )

    for t in periods:
        def avg_for(key):
            return m(r["per"][t][key] for r in res)

        print(
            f"{t:6d} | "
            f"{D['demand'][t]:6.0f} | "
            f"{avg_for('z'):5.3f} | "
            f"{avg_for('active'):6.2f} | "
            f"{avg_for('avail'):9.1f} | "
            f"{avg_for('used'):8.1f} | "
            f"{avg_for('idle'):8.1f} | "
            f"{avg_for('util'):6.2f}"
        )


if __name__ == "__main__":
    main("cost")
