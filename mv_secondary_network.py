"""Attach 20/0.4 kV secondary transformers below MV loads (CIGRE MV)."""

from __future__ import annotations

import math

import pandapower as pp
from pandapower.topology.graph_searches import calc_distance_to_bus

# Standard distribution-transformer ratings [kVA], ascending.
STANDARD_SN_KVA = (100, 360, 600)

# No-load losses [kW] per standard rating.
PFE_KW_BY_SN_KVA = {100: 0.55, 360: 0.85, 600: 1.2}

def pfe_kw_for_rating(unit_kva: int) -> float:
    """Return fixed iron losses [kW] for a standard secondary rating."""
    if unit_kva in PFE_KW_BY_SN_KVA:
        return PFE_KW_BY_SN_KVA[unit_kva]
    # Fallback for non-standard sizes: scale from 100 kVA rating.
    return PFE_KW_BY_SN_KVA[100] * unit_kva / 100.0


def select_standard_trafo_kva(
    required_kva: float,
    standard_sn_kva: tuple[int, ...] = STANDARD_SN_KVA,
) -> list[int]:
    """
    Pick fewest standard units (100 / 360 / 600 kVA), preferring larger sizes.

    Examples
    --------
    270 kVA -> [360]
    700 kVA -> [600, 100]
    970 kVA -> [600, 600]
    """
    if required_kva <= 0:
        return [standard_sn_kva[0]]

    sizes = sorted(standard_sn_kva)
    largest = sizes[-1]
    units: list[int] = []
    remaining = float(required_kva)

    while remaining > 1e-6:
        fit = next((s for s in sizes if s >= remaining), None)
        if fit is not None:
            units.append(fit)
            break
        units.append(largest)
        remaining -= largest

    return units


def attach_secondary_trafos_to_mv_loads(
    net,
    vn_mv_kv: float = 20.0,
    vn_lv_kv: float = 0.4,
    sn_margin: float = 1.0,
    standard_sn_kva: tuple[int, ...] = STANDARD_SN_KVA,
    skip_mv_buses: frozenset[int] | None = None,
) -> dict:
    """
    For each 20 kV bus that has load(s), create secondary transformer(s) using
    standard ratings (100 / 360 / 600 kVA by default) and move loads to 0.4 kV.

    Required apparent power per bus is ``sn_margin * sqrt(P^2 + Q^2)``; units are
    chosen greedily (e.g. 270 kVA -> one 360 kVA, not three 100 kVA).

    Returns
    -------
    dict mapping new trafo index -> list of load indices now on its LV side.
    """
    if net.bus.empty:
        raise ValueError("Empty network.")

    return _attach_secondary_trafos_to_mv_loads(
        net,
        vn_mv_kv=vn_mv_kv,
        vn_lv_kv=vn_lv_kv,
        sn_margin=sn_margin,
        standard_sn_kva=tuple(sorted(standard_sn_kva)),
        skip_mv_buses=skip_mv_buses,
    )


def _attach_secondary_trafos_to_mv_loads(
    net,
    vn_mv_kv: float,
    vn_lv_kv: float,
    sn_margin: float,
    standard_sn_kva: tuple[int, ...],
    skip_mv_buses: frozenset[int] | None = None,
) -> dict:
    mv_load_buses = []
    for bus in net.load["bus"].unique():
        bus = int(bus)
        if float(net.bus.at[bus, "vn_kv"]) == vn_mv_kv:
            mv_load_buses.append(bus)

    secondary_trafo_to_loads: dict[int, list] = {}
    next_bus = int(net.bus.index.max()) + 1

    for mv_bus in sorted(mv_load_buses):
        if skip_mv_buses and mv_bus in skip_mv_buses:
            continue
        load_idxs = net.load.index[net.load.bus == mv_bus].tolist()
        if not load_idxs:
            continue

        loads = net.load.loc[load_idxs]
        total_p = float(loads["p_mw"].sum())
        total_q = float(loads["q_mvar"].sum())
        s_mva = math.hypot(total_p, total_q)
        required_kva = sn_margin * s_mva * 1000.0
        unit_kva_list = select_standard_trafo_kva(required_kva, standard_sn_kva)
        total_sn_kva = sum(unit_kva_list)

        # Create LV buses and trafos first.
        unit_lv_buses: list[int] = []
        unit_trafo_idxs: list[int] = []
        for unit_kva in unit_kva_list:
            sn_mva = unit_kva / 1000.0
            lv_bus = next_bus
            next_bus += 1
            unit_lv_buses.append(lv_bus)

            pp.create_bus(net, vn_kv=vn_lv_kv, name=f"LV bus {lv_bus} (sec {unit_kva} kVA @ MV {mv_bus})")

            vkr_percent = 1.0
            vk_percent = 4.12
            pfe_kw = pfe_kw_for_rating(unit_kva)
            i0_percent = 0.08

            t_idx = pp.create_transformer_from_parameters(
                net,
                hv_bus=mv_bus,
                lv_bus=lv_bus,
                sn_mva=sn_mva,
                vn_hv_kv=vn_mv_kv,
                vn_lv_kv=vn_lv_kv,
                vk_percent=vk_percent,
                vkr_percent=vkr_percent,
                pfe_kw=pfe_kw,
                i0_percent=i0_percent,
                name=f"Sec {unit_kva} kVA MV{mv_bus}-LV{lv_bus}",
            )
            unit_trafo_idxs.append(int(t_idx))
            secondary_trafo_to_loads[int(t_idx)] = []

        # Split each MV load proportionally to installed kVA per unit.
        for lidx, row in loads.iterrows():
            for unit_kva, lv_bus, t_idx in zip(unit_kva_list, unit_lv_buses, unit_trafo_idxs):
                frac = unit_kva / total_sn_kva
                p_part = float(row["p_mw"]) * frac
                q_part = float(row["q_mvar"]) * frac
                if p_part == 0.0 and q_part == 0.0:
                    continue
                new_lidx = pp.create_load(
                    net,
                    bus=lv_bus,
                    p_mw=p_part,
                    q_mvar=q_part,
                    name=f"{row['name']} (sec {unit_kva} kVA @ MV{mv_bus})",
                )
                secondary_trafo_to_loads[t_idx].append(int(new_lidx))

        net.load.drop(load_idxs, inplace=True)

    return secondary_trafo_to_loads


def summarize_trafos(net) -> None:
    """Print primary (110/20) and secondary (20/0.4) transformers."""
    rows = []
    for t_idx, tr in net.trafo.iterrows():
        vn_hv = float(tr["vn_hv_kv"])
        kind = "primary" if vn_hv > 50 else "secondary"
        loads = net.load.index[net.load.bus == tr["lv_bus"]].tolist()
        p_sum = float(net.load.loc[loads, "p_mw"].sum()) if loads else 0.0
        rows.append(
            {
                "trafo": t_idx,
                "kind": kind,
                "hv_bus": int(tr["hv_bus"]),
                "lv_bus": int(tr["lv_bus"]),
                "sn_kva": round(float(tr["sn_mva"]) * 1000, 0),
                "sn_mva": float(tr["sn_mva"]),
                "n_loads": len(loads),
                "p_load_mw": round(p_sum, 4),
            }
        )
    import pandas as pd

    print(pd.DataFrame(rows).to_string(index=False))


def _is_primary_trafo(net, t_idx: int) -> bool:
    return float(net.trafo.at[t_idx, "vn_hv_kv"]) > 50.0


def build_trafo_to_loads(net) -> dict[int, list]:
    """
    Map each transformer to the load indices it serves.

    - Secondary (20/0.4 kV): loads on its LV bus.
    - Primary (110/20 kV): all loads on LV buses fed by secondaries whose
      HV bus lies on the primary MV feeder, plus any loads that remained
      directly on the MV feeder buses (e.g. skipped/non-controllable loads).
    """
    slack_bus = int(net.ext_grid.bus.iloc[0])
    trafo_to_loads: dict[int, list] = {}

    secondary_mask = net.trafo.vn_hv_kv <= 50
    primary_mask = ~secondary_mask

    for t_idx in net.trafo.index[secondary_mask]:
        lv_bus = int(net.trafo.at[t_idx, "lv_bus"])
        trafo_to_loads[int(t_idx)] = net.load.index[net.load.bus == lv_bus].tolist()

    for t_idx in net.trafo.index[primary_mask]:
        trafo = net.trafo.loc[t_idx]
        primary_hv_buses = net.trafo.loc[primary_mask, "hv_bus"]
        other_hv = [b for b in primary_hv_buses if b != trafo.hv_bus]
        notrav = list(set(other_hv)) + [slack_bus]
        feeder_mv_buses = calc_distance_to_bus(net, trafo.lv_bus, notravbuses=notrav).index

        sec_trafos = net.trafo[secondary_mask & net.trafo.hv_bus.isin(feeder_mv_buses)]
        load_idxs: list = []
        for _, sec in sec_trafos.iterrows():
            lv_bus = int(sec.lv_bus)
            load_idxs.extend(net.load.index[net.load.bus == lv_bus].tolist())

        # Include loads that remained directly on the MV feeder buses (fixed,
        # non-controllable loads with no secondary transformer).
        mv_direct = net.load.index[net.load.bus.isin(feeder_mv_buses)].tolist()
        for lidx in mv_direct:
            if lidx not in load_idxs:
                load_idxs.append(lidx)

        trafo_to_loads[int(t_idx)] = load_idxs

    return trafo_to_loads

def feeder_mv_buses(net, primary_idx: int) -> list[int]:
    """MV buses electrically downstream of one primary transformer LV bus."""
    slack_bus = int(net.ext_grid.bus.iloc[0])
    primary_mask = net.trafo.vn_hv_kv > 50
    trafo = net.trafo.loc[primary_idx]
    other_hv = [
        int(b) for b in net.trafo.loc[primary_mask, "hv_bus"].unique() if b != trafo.hv_bus
    ]
    notrav = list(set(other_hv)) + [slack_bus]
    return [int(b) for b in calc_distance_to_bus(net, trafo.lv_bus, notravbuses=notrav).index]

def secondary_trafo_indices_on_feeder(net, primary_idx: int) -> list[int]:
    """Secondary 20/0.4 kV transformers on the MV feeder of ``primary_idx``."""
    mv_buses = set(feeder_mv_buses(net, primary_idx))
    mask = net.trafo.vn_hv_kv <= 50
    sec = net.trafo[mask & net.trafo.hv_bus.isin(mv_buses)]
    return [int(i) for i in sec.index]
