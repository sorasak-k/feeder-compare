# Stat Cap Compare

A local Streamlit app for checking whether the **feeder service** and the **stat-cap service** agree on vehicle
capacity. You export a CSV log from each side, upload them, and the app pairs the readings up and highlights every
disagreement.

Nothing is stored or sent anywhere — CSVs are read in memory and the app runs on your own machine.

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

Open <http://localhost:8501>. Per-OS setup steps are in [doc/INSTALL.md](doc/INSTALL.md).

## Pages

The sidebar groups the pages into **Test** and **Dev**.

### Test

| Page                       | Purpose                                                                  | Inputs                |
|----------------------------|--------------------------------------------------------------------------|-----------------------|
| **Compare Cross-Counting** | Reconcile readings, accounting for cross-counted (split) route A→B rows  | feeder + stat-cap CSV |
| **Generate SQL**           | Produce the three queries that export those CSVs                         | op_id + date          |

### Dev

| Page                  | Purpose                                                            | Inputs                             |
|-----------------------|--------------------------------------------------------------------|------------------------------------|
| **Session Filter**    | Browse and filter the session log, including network-id columns    | session CSV                        |
| **Stat Cap Filter**   | Browse and filter the stat-cap log                                 | stat-cap CSV                       |
| **Feeder Cap Filter** | Browse and filter the feeder log                                   | feeder CSV                         |
| **Sum Filter**        | Sum inc/dec after filtering by vhc, network, node, and session     | session + (feeder or stat-cap) CSV |

## How the comparison works

Rows are joined on `op_id`, `vhc_id`, and a timestamp:

- feeder side — `add_at`
- stat-cap side — `coalesce(src_at, mod_at)`, i.e. `src_at` when present, `mod_at` when it is empty or the column is
  missing

The join is an outer join, so every reading survives and gets a status (see below). Matching is exact to the
millisecond, so two events that describe the same thing a millisecond apart appear as a `feeder_only` / `stat_only`
pair rather than a mismatch.

**Mismatch vs. unmatched:** a *mismatch* means the reading is in both logs but a value differs — feeder changed a
number. *Unmatched* (`feeder_only` / `stat_only`) means the reading is in only one log, so nothing was compared — it
was lost, or the timestamps do not line up. See [doc/USAGE.md](doc/USAGE.md#mismatch-vs-unmatched) for examples.

### Split readings

A reading taken at a stop shared by two routes is legitimately written by the feeder as **two** rows — an alighting
half on route A (`inc` zeroed) and a boarding half on route B (`dec` zeroed). The comparison therefore works on
**readings**, not rows: feeder rows sharing `op_id` + `vhc_id` + `add_at` are collapsed (`inc` and `dec` summed,
`cur` taken once) before the join.

| `row_status`     | Feeder rows | Meaning                                                      | Colour    |
|------------------|-------------|--------------------------------------------------------------|-----------|
| `match`          | 1           | values identical to stat-cap                                 | green     |
| `split_match`    | 2           | a cross-counted split whose halves add back up to stat-cap   | blue      |
| `mismatch`       | 1           | a value differs                                              | red       |
| `split_mismatch` | 2           | a split whose halves do not add back up                      | light red |
| `fault`          | 3+          | more rows than a split can produce — never expected          | dark red  |
| `feeder_only`    | 1+          | no stat-cap counterpart                                      | amber     |
| `stat_only`      | 0           | no feeder counterpart                                        | amber     |

The page shows **Feeder rows** and **Stat-cap rows** (the uploaded files), **Readings** (the joined result, one per
reading — lower than feeder rows by one per split), and a breakdown that adds up to Readings: **Match**,
**Split match**, **Mismatch** (`mismatch` + `split_mismatch`), **Fault**, and **Unmatched** (`feeder_only` +
`stat_only`). A **Route A → Route B counter** shows how often each route pair cross-counted.
Worked examples and known gaps are in [doc/USAGE.md](doc/USAGE.md#compare-cross-counting).

## Getting the data

The **Generate SQL** page writes the three export queries for you. Give it an `op_id`
(default `52`) and a start and end date/time; the range is entered in **Asia/Bangkok** (GMT+7) but converted to UTC
before substitution, so `2026-10-10 08:30` → `2026-10-12 20:00` becomes `start_time = '2026-10-10 01:30:00'` and
`end_time = '2026-10-12 13:00:00'`. The end is exclusive.

Run the queries, save the results as CSV, then upload them on a comparison page.

## Layout

```
app.py                  # entry point — page navigation
common.py               # CSV loading, session filtering, comparison, SQL templates
requirements.txt        # pinned: streamlit 1.61.1, pandas 3.0.5 (Python 3.14.4)
pages/                  # one file per page
doc/                    # INSTALL, USAGE, and the cross-counting explainer
example_data/           # sample CSVs and the source SQL template
data/                   # your own exports (not tracked in git)
```

## Documentation

- [doc/INSTALL.md](doc/INSTALL.md) — requirements, per-OS setup, run options, troubleshooting
- [doc/USAGE.md](doc/USAGE.md) — input formats, every page in detail, reading results, workflow
- [doc/feeder_stat_cap_cross_counting_explained.md](doc/feeder_stat_cap_cross_counting_explained.md) — how and when
  the feeder splits a reading into two rows (cross-counting)
