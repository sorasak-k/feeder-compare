# Using Stat Cap Compare

The app answers one question: **do the feeder service and the stat-cap service agree on vehicle capacity?** You upload
the CSV log from each side, and the app pairs the readings up and highlights every disagreement.

See [INSTALL.md](INSTALL.md) to get it running. Start it with:

```bash
streamlit run app.py
```

Then pick a page from the sidebar.

## The six pages

| Page                       | What it does                                                                 | Files needed                       |
|----------------------------|------------------------------------------------------------------------------|------------------------------------|
| **Compare Cross-Counting** | Reconciles readings, accounting for cross-counted (split) route A→B rows     | feeder + stat-cap                  |
| **Generate SQL**           | Produces the three export queries that yield those CSVs                      | none                               |
| **Session Filter**         | Browses and filters the session log on its own                               | session                            |
| **Stat Cap Filter**        | Browses and filters the stat-cap log on its own                              | stat-cap                           |
| **Feeder Cap Filter**      | Browses and filters the feeder log on its own                                | feeder                             |
| **Sum Filter**             | Sums `inc`/`dec` after filtering by vhc, network, node, and session          | session + (feeder or stat-cap)     |

## Input files

All inputs are CSV. Surrounding whitespace and stray quotes around values and headers are stripped on load, so exports
with `"op_id", "vhc_id"`-style padding work as-is.

### Feeder log — e.g. `feeder_vehicle_stat_cap_log.csv`

Required columns:

- `op_id`, `vhc_id` — the key pair identifying an operation and a vehicle
- `add_at` — the event timestamp used for matching
- `cur`, `inc`, `dec` — the capacity values being compared

Extra columns (`net_id`, `lon`, `lat`, …) are ignored.

### Stat-cap log — e.g. `vehicle_stat_cap_log.csv`

Required columns:

- `op_id`, `vhc_id`
- `src_at` — source timestamp, the one matched against the feeder's `add_at`
- `mod_at` — modification timestamp, used wherever `src_at` is empty (the column may be missing altogether, in which
  case `mod_at` is used for every row)
- `cur`, `inc`, `dec`

### Session log — e.g. `session.csv`

Required columns:

- `op_id`, `vhc_id`
- `add_at`, `end_at` — the start and end of the session window
- `is_tali` — boolean, used by the `is_tali` filter on the Sum Filter page

Timestamps are parsed leniently (mixed formats are accepted) and truncated to milliseconds, so
`2026-07-19 00:00:16.048973` and `2026-07-10T15:27:57` both work. Unparseable timestamps become empty and will not match
anything.

Ready-made samples live in `example_data/`.

## How the comparison works

1. Both logs are keyed on `op_id`, `vhc_id`, and a timestamp:
    - feeder side uses `add_at`
    - stat-cap side uses `coalesce(src_at, mod_at)` — `src_at` when it has a value,
      `mod_at` when `src_at` is empty or the column is absent entirely

   Sum Filter uses the same rule for session-window filtering. The resulting column is displayed as `src_at`.
2. Feeder rows sharing that key are collapsed into one reading, because the feeder may legitimately split one reading
   into two rows (see [Compare Cross-Counting](#compare-cross-counting)).
3. The two sides are outer-joined on that key, so nothing is dropped, and each reading gets a `row_status` — see
   [Result statuses](#result-statuses).

Matching is exact on the millisecond. A feeder event and a stat-cap event that describe the same thing one millisecond
apart show up as a `feeder_only` / `stat_only` pair, not as a mismatch — worth remembering when you read the results.

### Mismatch vs. unmatched

The two problem groups mean different things:

| Group         | Statuses                                                        | In both files? | Values compared?     | Usual cause                                                                                   |
|---------------|-----------------------------------------------------------------|----------------|----------------------|-----------------------------------------------------------------------------------------------|
| **Mismatch**  | `mismatch`, `split_mismatch`                                    | yes            | yes — and they differ | feeder **changed**, lost, or duplicated a counter value while passing the reading through     |
| **Unmatched** | `feeder_only`, `stat_only`                                      | no — one side  | no                   | the reading was **lost**, the timestamps do not line up exactly, or the exports cover different vehicles |

**Mismatch** — both logs have a reading at the same `op_id` + `vhc_id` + timestamp, but at least one of `cur`, `inc`,
`dec` differs:

| Side     | `cur` | `inc` | `dec` |
|----------|-------|-------|-------|
| stat-cap | 20    | 5     | 8     |
| feeder   | 20    | 5     | **7** |

**Unmatched** — only one log has a reading at that `op_id` + `vhc_id` + timestamp, so there is nothing to compare
against:

- `feeder_only` — feeder has the reading, stat-cap does not
- `stat_only` — stat-cap has the reading, feeder does not

| Side     | timestamp      | `cur` | `inc` | `dec` |
|----------|----------------|-------|-------|-------|
| stat-cap | `10:00:00.120` | 20    | 5     | 8     |
| feeder   | —              | —     | —     | —     |

A mismatch is evidence that feeder computed something wrong. A large number of unmatched rows is more often a
timestamp problem than real data loss — check for a `feeder_only` and a `stat_only` row on the same vehicle a few
milliseconds apart before treating them as missing events.

## Page walkthroughs

### Compare Cross-Counting

Upload the feeder log and the stat-cap log — no session file needed. The page does not assume one feeder row per
stat-cap reading: a reading taken at a stop shared by two routes (a vehicle ending a run
on route A and starting one on route B) is legitimately written by the feeder service as **two** rows, one per route —
see `feeder_stat_cap_cross_counting_explained.md` for the full explanation.

#### How a reading is reconstructed

The unit of comparison is a **reading**, not a row. Feeder rows are grouped by `op_id` + `vhc_id` + `add_at`, and
each group is collapsed back into the single source reading it came from:

| Value              | Built from                                   | Why                                                    |
|--------------------|----------------------------------------------|--------------------------------------------------------|
| `feeder_row_count` | number of feeder rows in the group           | 1 = normal, 2 = split, 3+ = fault                      |
| `feeder_inc`       | **sum** of `inc` across the group            | a split moves `inc` to the boarding half, never copies it |
| `feeder_dec`       | **sum** of `dec` across the group            | a split moves `dec` to the alighting half              |
| `feeder_cur`       | `cur` of the **first** row only              | a split copies `cur` onto both halves — summing would double it |

The reconstructed reading is then outer-joined to stat-cap on `op_id` + `vhc_id` + `src_at` (the timestamp rule
under [How the comparison works](#how-the-comparison-works)), and `cur`, `inc`, `dec` must be identical on both sides. A missing value on either side counts as
`0`.

#### Metrics

The first row describes the inputs, the second breaks **Readings** down by result:

| Metric                         | Counts                                                                   |
|--------------------------------|--------------------------------------------------------------------------|
| **Feeder rows**                | rows in the uploaded feeder CSV                                          |
| **Stat-cap rows**              | rows in the uploaded stat-cap CSV                                        |
| **Readings**                   | rows of the joined result — one per reading, from either side            |
| **Match**                      | `match` readings                                                         |
| **Split match**                | `split_match` readings                                                   |
| **Mismatch**                   | `mismatch` **plus** `split_mismatch` readings                            |
| **Fault (3+ rows)**            | `fault` readings                                                         |
| **Unmatched (no counterpart)** | `feeder_only` **plus** `stat_only` readings                              |

The second row always adds up to **Readings**. **Readings** is usually lower than **Feeder rows**, because each
split reading collapses two feeder rows into one (and a `fault` reading collapses three or more). The metrics
always reflect the whole result, not the filtered view.

#### Result statuses

| `row_status`     | Feeder rows | Meaning                                                                                  | Row colour |
|------------------|-------------|------------------------------------------------------------------------------------------|------------|
| `match`          | 1           | Normal reading; `cur`/`inc`/`dec` identical to stat-cap                                   | green      |
| `split_match`    | 2           | Cross-counted reading; the two halves add back up to the stat-cap reading                | blue       |
| `mismatch`       | 1           | Normal reading, but at least one of `cur`/`inc`/`dec` differs from stat-cap              | red        |
| `split_mismatch` | 2           | Cross-counted reading whose halves do **not** add back up to stat-cap                    | light red  |
| `fault`          | 3+          | More rows than a split can produce — values are not compared; always a bug               | dark red   |
| `feeder_only`    | 1+          | Feeder wrote the reading, but stat-cap has nothing at that key and timestamp             | amber      |
| `stat_only`      | 0           | Stat-cap has the reading, but feeder wrote no row for it                                  | amber      |

Examples, for a stat-cap reading of `cur=20, inc=5, dec=8`:

| Feeder rows (`cur` / `inc` / `dec`)      | Reconstructed   | `row_status`     |
|------------------------------------------|-----------------|------------------|
| `20/5/8`                                 | `20/5/8`        | `match`          |
| `20/5/7`                                 | `20/5/7`        | `mismatch`       |
| `20/0/8` + `20/5/0`                      | `20/5/8`        | `split_match`    |
| `20/0/8` + `20/4/0`                      | `20/4/8`        | `split_mismatch` |
| `20/5/8` + `20/5/0` (inc not zeroed on A) | `20/10/8`       | `split_mismatch` |
| three rows at the same `add_at`          | —               | `fault`          |

What the problem statuses usually point to:

- **`mismatch`** — feeder altered a reading it should have passed through unchanged.
- **`split_mismatch`** — feeder split the reading but lost, duplicated, or failed to zero a counter on one half.
- **`fault`** — duplicate writes, or the feeder export mixes several `rule_op_id`s (the Generate SQL query filters on
  one, so this should not happen with its output).
- **`feeder_only` / `stat_only`** — usually a timestamp offset. `feeder_only` also appears
  for vehicles an operator monitors but does not own: the feeder export filters on `rule_op_id`, the stat-cap export
  on `op_id`.

Known gaps in the check: `cur` is read from the first feeder row only, so two halves carrying different `cur` values
are not caught; and only the totals are compared, so a split whose halves are shaped wrongly (e.g. `inc` on both
halves) but still sums correctly shows as `split_match`.

#### Route A → Route B counter

For each split reading the two halves are told apart: the half with only `dec` is **route A** (the alighting half,
the run that is ending) and the half with only `inc` is **route B** (the boarding half, the run that is starting). If
both counters are zero, the half whose reading time is closest to its `session_end_at` is taken as route A. The
`net_id`, `net_ver`, `seq`, and `nod_id` of each half are stored as `route_a_*` / `route_b_*` columns.

The counter table groups split readings by `route_a_net_id`, `route_a_nod_id`, `route_b_net_id`, `route_b_nod_id`
and shows how many times each transition occurred, most frequent first. It needs a `session_end_at` column in the
feeder CSV; without it splits are still counted in the statuses, but the route columns stay empty.

#### Table

```
op_id | vhc_id | add_at | feeder_row_count | feeder_cur | feeder_inc | feeder_dec | route_a_* | route_b_* | src_at | stat_cur | stat_inc | stat_dec | row_status
```

The `op_id` / `vhc_id` pills narrow the table (selecting nothing means *all*), and a `row_status` multiselect
chooses which statuses are shown — everything except `match` by default. Sort by clicking a header; use the table's
built-in search and download-as-CSV controls in its top-right corner to export what you are looking at.

Use it for: telling a genuine mismatch apart from a correctly cross-counted split, and for auditing which route pairs
are cross-counting and how often.

### Session Filter

Upload just the session log. You get:

- `op_id`, `vhc_id`, and — since `session.csv` includes them — `sys_id`, `lyr_id`, `net_id` multi-selects (all
  selected by default)
- range sliders for `add_at` and `end_at`
- a caption reporting how many of the total sessions are shown
- the filtered session table

Use it for: finding the session windows worth investigating.

### Stat Cap Filter

Upload just the stat-cap log. You get:

- `op_id` and `vhc_id` multi-selects (all selected by default)
- range sliders for `mod_at` and, if present, `src_at`
- a caption reporting how many of the total stat-cap rows are shown
- the filtered stat-cap table

Use it for: spot-checking the stat-cap export on its own before pairing it with a feeder log.

### Feeder Cap Filter

Upload just the feeder log. You get:

- multi-selects for `op_id`, `vhc_id`, and whichever of `net_sys_id`, `net_lyr_id`, `net_id`, `nod_sys_id`,
  `nod_lyr_id`, `nod_id` are present (all selected by default)
- a range slider for `add_at`
- a caption reporting how many of the total feeder rows are shown
- the filtered feeder table

Use it for: narrowing a feeder export down to a specific network or node before comparing it against stat-cap.

### Generate SQL

Produces the three `select` statements that export the CSVs the other pages consume — so you start here, run the queries
against the database, then come back with the results.

Two inputs:

- **op_id** — the operation to export, default `52`
- **Start date** / **Start time** — the beginning of the window, defaults to today at `00:00`
- **End date** / **End time** — the end of the window, defaults to tomorrow at `00:00`

The four range inputs are entered in **Asia/Bangkok** (GMT+7) but the database stores UTC, so the page converts before
substituting: `2026-10-10 08:30` → `2026-10-12 20:00` local yields `start_time = '2026-10-10 01:30:00'` and
`end_time = '2026-10-12 13:00:00'`. The caption under the inputs always shows both conversions. Each query then covers
`start_time` to `end_time`, with the end **exclusive** — so the default today `00:00` → tomorrow `00:00` gives exactly
one local day. The time pickers step by one minute. If the end is not after the start, the page says so and generates
nothing.

The three queries, in the order they appear:

| Query                             | Table                         | Window                                                        |
|-----------------------------------|-------------------------------|---------------------------------------------------------------|
| `session.csv`                     | `vehicle_session_log`         | opens 30 days before `start_time`, still open at `start_time` |
| `feeder_vehicle_stat_cap_log.csv` | `feeder_vehicle_stat_cap_log` | `add_at` within the range                                     |
| `vehicle_stat_cap_log.csv`        | `vehicle_stat_cap_log`        | see below — two branches                                      |

The session query reaches back 30 days on purpose: a trip that started days earlier but was still running at
`start_time` has to be included, or rows on the day under examination would look like they fall outside every session.

The stat-cap query is an `OR` of two branches, because the row's own timestamp depends on whether `src_at` was recorded:

- `src_at` present → window on `src_at`, with `mod_at` allowed ±2 days outside the range (a row can be written well after
  the event it describes)
- `src_at is null` → nothing to window on, so `mod_at` itself must fall inside the range

Without the second branch the `src_at is null` rows would be dropped by the export, even though the comparison falls
back to `mod_at` for exactly those rows.

Copy a single query with the button in the top-right of its code block, or use **Download query.sql** to get all three
as one file named
`query_op<op_id>_<start>_<end>.sql`, where both stamps are the UTC window (e.g.
`query_op52_20261010-0130_20261012-1300.sql`).

The templates mirror `example_data/sql/query.sql` and live in `QUERY_TEMPLATES` in
`common.py`; edit them there if the schema changes.

## A typical workflow

1. Open **Generate SQL**, set the op_id and the Asia/Bangkok time range you are checking, and run the three queries
   against the database to get the CSVs.
2. Open **Compare Cross-Counting** and upload the feeder and stat-cap files. Check that the metrics reconcile:
   **Readings** should equal the stat-cap rows, and **Feeder rows** should equal **Readings** plus one per
   **Split match**.
3. If mismatches, faults, or unmatched readings appear, use the `op_id` / `vhc_id` pills to isolate one vehicle and
   read its readings in timestamp order.
4. Use the **Route A → Route B counter** to confirm that splits only happen between route pairs you expect.
5. Drill into a vehicle, network, or node with **Feeder Cap Filter**, **Stat Cap Filter**, or **Sum Filter** when a
   discrepancy needs a closer look.

## Tips and limits

- **Uploads are per page.** Switching pages clears the files; re-upload them on the new page.
- **Nothing is written to disk.** Uploads live in memory for the session only. Use the table's download button to keep a
  result.
- **Large results render slowly.** Every row is styled individually, so a table with hundreds of thousands of cells
  takes a while. Leave `match` out of the `row_status` selection, or narrow with the ID pills.
- **A wall of `feeder_only` / `stat_only` rows** usually means a timestamp problem — a clock offset between services, or
  a column parsed as empty — not thousands of genuinely missing events. Check a few raw rows in the CSV before treating
  it as data loss.
- **Missing required column** raises a `KeyError` in the app. Confirm the export includes the columns listed above under
  Input files.
