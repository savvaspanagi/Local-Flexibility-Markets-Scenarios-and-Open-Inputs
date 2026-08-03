# LFM Benchmark Open Inputs

Open inputs for benchmarking local flexibility market (LFM) methods on a modified CIGRE European MV network.

## Quick start

```bash
cd "Benchmark Open Inputs"
pip install -r requirements.txt
jupyter notebook supplementary.ipynb
```

Section 4 of the notebook calls `run_baseline_pf.py` and rebuilds `results_base/` and `results_stress/` from the published load profiles in `data/`. You can also run the power flow directly:

```bash
python run_baseline_pf.py
```

## Data files (`data/`)

| File | Description |
|------|-------------|
| `load_frac.csv` | Common duck-curve load factor [p.u.] |
| `base_load_P_mw.csv`, `base_load_Q_mvar.csv` | Hourly nodal P/Q for the base day |
| `stress_load_P_mw.csv`, `stress_load_Q_mvar.csv` | Hourly nodal P/Q for the stress (EV) day |
| `wholesale.csv` | Cyprus DAM prices used in the study [EUR/MWh] |
| `bids_offers.xlsx` | Synthetic FSP hourly offers (capacity + bid price) |
| `load_idxs.csv`, `secondary_trafo_idxs.csv` | Index maps |

Load columns are named `load_<pandapower_load_idx>`.

## Results files

Each of `results_base/` and `results_stress/` contains:

- `vm_min.csv` — network-wide minimum bus voltage [p.u.]
- `line_loading_percent.csv` — line loadings [%]
- `trafo_loading_percent.csv` — transformer loadings [%]

These can be regenerated at any time with `python run_baseline_pf.py`.

## Citation

If you use these inputs (network, scenarios, offers, or baseline results), please cite **both** the paper and this Zenodo repository:

**Paper**

> S. Panagi, C. Spanias, and P. Aristidou, “Dynamic Flexibility Requests in Local Flexibility Markets: Quantifying the DSO Willingness to Pay,” *IEEE Transactions on Energy Markets, Policy and Regulation*, 2026, under review.

```bibtex
@article{panagi2026dynamic,
  author  = {Panagi, Savvas and Spanias, Chrysovalantis and Aristidou, Petros},
  title   = {Dynamic Flexibility Requests in Local Flexibility Markets: Quantifying the {DSO} Willingness to Pay},
  journal = {IEEE Transactions on Energy Markets, Policy and Regulation},
  year    = {2026},
  note    = {Under review},
}
```

**Dataset (this repository)**

> S. Panagi, C. Spanias, and P. Aristidou, “Benchmarking Case Study for Local Flexibility Markets: Network, Scenarios, and Open Inputs,” Zenodo, 2026. DOI: [10.5281/zenodo.XXXXXXX](https://doi.org/10.5281/zenodo.XXXXXXX).

```bibtex
@misc{panagi2026zenodo,
  author       = {Panagi, Savvas and Spanias, Chrysovalantis and Aristidou, Petros},
  title        = {Benchmarking Case Study for Local Flexibility Markets: Network, Scenarios, and Open Inputs},
  year         = {2026},
  howpublished = {Zenodo},
  doi          = {10.5281/zenodo.XXXXXXX},
}
```