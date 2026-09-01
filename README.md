# Stat Cap Compare

A local Streamlit app for checking whether the **feeder service** and the **stat-cap service** agree on vehicle
capacity. You export a CSV log from each side, upload them, and the app pairs the rows up and highlights every
disagreement.

Nothing is stored or sent anywhere — CSVs are read in memory and the app runs on your own machine.

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

Open <http://localhost:8501>. Per-OS setup steps are in [INSTALL.md](INSTALL.md).

## Pages

| Page                             | Purpose                                           | Inputs                          |
|----------------------------------|---------------------------------------------------|---------------------------------|
| **Compare Stat Only**            | Compare every row in both logs, ignoring sessions | feeder + stat-cap CSV           |
| **Compare Stat with Session**    | Compare only rows inside a session window         | session + feeder + stat-cap CSV |
| **Compare Stat Outside Session** | Compare only rows outside every session window    | session + feeder + stat-cap CSV |
| **Session Filter**               | Browse and filter the session log, including network-id columns | session CSV       |
| **Stat Cap Filter**              | Browse and filter the stat-cap log                | stat-cap CSV                    |
| **Feeder Cap Filter**            | Browse and filter the feeder log                  | feeder CSV                      |
| **Generate SQL**                 | Produce the three queries that export those CSVs  | op_id + date                    |

## How the comparison works

Rows are joined on `op_id`, `vhc_id`, and a timestamp:

- feeder side — `add_at`
- stat-cap side — `coalesce(src_at, mod_at)`, i.e. `src_at` when present, `mod_at` when it is empty or the column is
  missing

The join is an outer join, so every row survives and gets a status:

| `row_status`  | Meaning                                         | Colour |
|---------------|-------------------------------------------------|--------|
| `match`       | both sides present, `cur`/`inc`/`dec` identical | green  |
| `mismatch`    | both sides present, a value differs             | red    |
| `feeder_only` | no stat-cap counterpart                         | amber  |
| `stat_only`   | no feeder counterpart                           | amber  |

Matching is exact to the millisecond, so two events that describe the same thing a millisecond apart appear as a
`feeder_only` / `stat_only` pair rather than a mismatch.

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
example_data/           # sample CSVs and the source SQL template
data/                   # your own exports (not tracked in git)
```

## Documentation

- [INSTALL.md](INSTALL.md) — requirements, per-OS setup, run options, troubleshooting
- [USAGE.md](USAGE.md) — input formats, every page in detail, reading results, workflow
