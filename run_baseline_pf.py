#!/usr/bin/env python3
"""Run 24 h baseline AC power flows for the base and stress days.

Reads load time series from ``data/`` and writes:
  results_base/{vm_min,line_loading_percent,trafo_loading_percent}.csv
  results_stress/...

Usage (from this folder)::

    python run_baseline_pf.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pandapower as pp
import pandapower.networks as pn

from mv_secondary_network import attach_secondary_trafos_to_mv_loads

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
FIXED_MV_BUSES = frozenset({1, 12})


def build_network():
    net = pn.create_cigre_network_mv()
    net.trafo.loc[0, "pfe_kw"] = 22
    net.trafo.loc[1, "pfe_kw"] = 22
    attach_secondary_trafos_to_mv_loads(net, skip_mv_buses=FIXED_MV_BUSES)
    return net


def load_pq(scenario: str) -> tuple[pd.DataFrame, pd.DataFrame, list[int]]:
    """Return (P_mw, Q_mvar) DataFrames indexed by hour, columns = load indices."""
    p = pd.read_csv(DATA / f"{scenario}_load_P_mw.csv")
    q = pd.read_csv(DATA / f"{scenario}_load_Q_mvar.csv")
    load_idxs = [int(c.split("_", 1)[1]) for c in p.columns if c.startswith("load_")]
    P = p[[f"load_{i}" for i in load_idxs]].copy()
    Q = q[[f"load_{i}" for i in load_idxs]].copy()
    P.columns = load_idxs
    Q.columns = load_idxs
    return P, Q, load_idxs


def run_scenario(scenario: str) -> dict[str, np.ndarray]:
    net = build_network()
    P, Q, load_idxs = load_pq(scenario)
    n_steps = len(P)
    n_lines = len(net.line)
    n_trafos = len(net.trafo)

    vm_min = np.zeros(n_steps)
    line_loading = np.zeros((n_steps, n_lines))
    trafo_loading = np.zeros((n_steps, n_trafos))

    for t in range(n_steps):
        for lid in load_idxs:
            net.load.at[lid, "p_mw"] = float(P.at[t, lid])
            net.load.at[lid, "q_mvar"] = float(Q.at[t, lid])
        pp.runpp(net, calculate_voltage_angles=True)
        vm_min[t] = float(net.res_bus.vm_pu.min())
        line_loading[t, :] = net.res_line.loading_percent.to_numpy(dtype=float)
        trafo_loading[t, :] = net.res_trafo.loading_percent.to_numpy(dtype=float)
        print(f"  {scenario} hour {t:02d}: Vmin={vm_min[t]:.4f} p.u., "
              f"max line={line_loading[t].max():.1f}%, max trafo={trafo_loading[t].max():.1f}%")

    return {
        "vm_min": vm_min,
        "line_loading": line_loading,
        "trafo_loading": trafo_loading,
    }


def write_results(scenario: str, res: dict[str, np.ndarray]) -> Path:
    out = ROOT / f"results_{scenario}"
    out.mkdir(exist_ok=True)
    hours = np.arange(len(res["vm_min"]))

    pd.DataFrame({"hour": hours, "vm_min_pu": res["vm_min"]}).to_csv(
        out / "vm_min.csv", index=False
    )

    ll = pd.DataFrame(
        res["line_loading"],
        columns=[f"line_{i}" for i in range(res["line_loading"].shape[1])],
    )
    ll.insert(0, "hour", hours)
    ll.to_csv(out / "line_loading_percent.csv", index=False)

    tl = pd.DataFrame(
        res["trafo_loading"],
        columns=[f"trafo_{i}" for i in range(res["trafo_loading"].shape[1])],
    )
    tl.insert(0, "hour", hours)
    tl.to_csv(out / "trafo_loading_percent.csv", index=False)

    print(f"wrote {out}")
    return out


def main():
    if not DATA.is_dir():
        raise SystemExit(f"Missing data folder: {DATA}")

    for scenario in ("base", "stress"):
        print(f"=== Running {scenario} baseline AC power flow ===")
        res = run_scenario(scenario)
        write_results(scenario, res)

    print("Done.")


if __name__ == "__main__":
    main()
