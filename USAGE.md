# Using Stat Cap Compare

The app answers one question: **do the feeder service and the stat-cap service agree on
vehicle capacity?** You upload the CSV log from each side, and the app pairs the rows up
and highlights every disagreement.

See [INSTALL.md](INSTALL.md) to get it running. Start it with:

```bash
streamlit run app.py
```

Then pick a page from the sidebar.

## The five pages

| Page | What it does | Files needed |
|------|--------------|--------------|
| **Compare Stat Only** | Compares every row in both logs, ignoring sessions | feeder + stat-cap |
| **Compare Stat with Session** | Compares only rows that fall inside a session window | session + feeder + stat-cap |
| **Compare Stat Outside Session** | Compares only rows that fall outside every session window | session + feeder + stat-cap |
| **Session Filter** | Browses and filters the session log on its own | session |
| **Generate SQL** | Produces the three export queries that yield those CSVs | none |

## Input files

All inputs are CSV. Surrounding whitespace and stray quotes around values and headers are
stripped on load, so exports with `"op_id", "vhc_id"`-style padding work as-is.

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
- `mod_at` — modification timestamp, used wherever `src_at` is empty (the column may be
  missing altogether, in which case `mod_at` is used for every row)
- `cur`, `inc`, `dec`

### Session log — e.g. `session.csv`

Required columns:

- `op_id`, `vhc_id`
- `add_at`, `end_at` — the start and end of the session window
- `is_tali` — boolean, used by the `is_tali` filter on the session pages

Timestamps are parsed leniently (mixed formats are accepted) and truncated to
milliseconds, so `2026-07-19 00:00:16.048973` and `2026-07-10T15:27:57` both work.
Unparseable timestamps become empty and will not match anything.

Ready-made samples live in `example_data/`.

## How the comparison works

1. Both logs are keyed on `op_id`, `vhc_id`, and a timestamp:
   - feeder side uses `add_at`
   - stat-cap side uses `coalesce(src_at, mod_at)` — `src_at` when it has a value,
     `mod_at` when `src_at` is empty or the column is absent entirely

   This is the same rule on all three comparison pages, and the session pages use it for
   session-window filtering too. The resulting column is displayed as `src_at`.
2. The two sides are outer-joined on that key, so nothing is dropped.
3. Each resulting row is labelled:

| `row_status` | Meaning | Row colour |
|--------------|---------|------------|
| `match` | Both sides present, `cur`/`inc`/`dec` identical | green |
| `mismatch` | Both sides present, at least one value differs | red |
| `feeder_only` | No stat-cap row at that key and timestamp | amber |
| `stat_only` | No feeder row at that key and timestamp | amber |

Matching is exact on the millisecond. A feeder event and a stat-cap event that describe
the same thing one millisecond apart show up as a `feeder_only` / `stat_only` pair, not
as a mismatch — worth remembering when you read the results.

## Reading the results

Every comparison page shows the same three sections.

### Metrics

- **Total rows compared** — rows in the joined result
- **Matches** — rows where both sides agree
- **Mismatches** — rows where both sides exist but values differ
- **Unmatched (no counterpart)** — the `feeder_only` plus `stat_only` rows

These counts always reflect the whole result, not the filtered view below.

### Filters

- **op_id / vhc_id pills** — click to narrow the table to specific IDs. Selecting nothing
  means *all*, which is the default.
- **Show only diffs** (on by default) — hides `match` rows so only problems remain.
- **Show feeder-only** / **Show stat-cap-only** — toggle the unmatched rows in or out.

To see everything including the matches, untick *Show only diffs*.

### Table

Columns are laid out for side-by-side reading:

```
op_id | vhc_id | cur_feeder | cur_stat | inc_feeder | inc_stat | dec_feeder | dec_stat | add_at | src_at | row_status | [session columns]
```

On the session pages, four extra columns show which session a row landed in:
`session_add_at`, `session_end_at`, `session_op_id`, `session_vhc_id`.

Sort by clicking a header; use the table's built-in search and download-as-CSV controls
in its top-right corner to export what you are looking at.

## Page walkthroughs

### Compare Stat Only

Upload the feeder log and the stat-cap log. This is the widest comparison — it covers
every logged row regardless of whether a session was active.

Use it for: a first pass over a day of data, or when you have no session export.

Like the session pages, it matches the feeder's `add_at` against the stat-cap
`coalesce(src_at, mod_at)` — `src_at` is the timestamp the event originated at, so it
lines up with `add_at` more directly than `mod_at` does.

### Compare Stat with Session

Upload the session log first, then the two capacity logs.

An `is_tali` selector appears above the results — leave it on **All**, or pick **True** /
**False** to restrict the comparison to those sessions.

Only rows whose timestamp falls between a session's `add_at` and `end_at` (for the same
`op_id` + `vhc_id`) are compared. If a row falls inside several overlapping sessions, the
first matching one is attributed to it.

Use it for: verifying behaviour during actual trips, where discrepancies matter most.

### Compare Stat Outside Session

Same three uploads and the same `is_tali` selector, but the filter is inverted: only rows
that fall inside *no* session window are compared.

Use it for: catching capacity events logged when no trip was in progress — often a sign
of stale or replayed data.

### Session Filter

Upload just the session log. You get:

- `op_id` and `vhc_id` multi-selects (all selected by default)
- range sliders for `add_at` and `end_at`
- a caption reporting how many of the total sessions are shown
- the filtered session table

Use it for: finding the session windows worth investigating, before going back to a
comparison page.

### Generate SQL

Produces the three `select` statements that export the CSVs the other pages consume — so
you start here, run the queries against the database, then come back with the results.

Two inputs:

- **op_id** — the operation to export, default `52`
- **Date (GMT+7)** — the local day you want, defaults to today

The date is entered in local **GMT+7** time but the database stores UTC, so the page
converts before substituting. Picking `2026-10-10` yields a `start_time` of
`2026-10-09 17:00:00`, and the caption under the inputs always shows the conversion it
applied. Each query then covers `start_time` to `start_time + 1 day`, i.e. exactly the
local day you asked for.

The three queries, in the order they appear:

| Query | Table | Window |
|-------|-------|--------|
| `session.csv` | `vehicle_session_log` | opens 30 days before `start_time`, still open at `start_time` |
| `feeder_vehicle_stat_cap_log.csv` | `feeder_vehicle_stat_cap_log` | `add_at` within the day |
| `vehicle_stat_cap_log.csv` | `vehicle_stat_cap_log` | `src_at` within the day, `mod_at` within ±1 day |

The session query reaches back 30 days on purpose: a trip that started days earlier but
was still running at `start_time` has to be included, or rows on the day under
examination would look like they fall outside every session.

Copy a single query with the button in the top-right of its code block, or use
**Download query.sql** to get all three as one file named
`query_op<op_id>_<date>.sql`.

The templates mirror `example_data/sql/query.sql` and live in `QUERY_TEMPLATES` in
`common.py`; edit them there if the schema changes.

## A typical workflow

1. Open **Generate SQL**, set the op_id and the GMT+7 date you are checking, and run the
   three queries against the database to get the CSVs.
2. Open **Session Filter**, confirm the sessions look sane, and note the `op_id` /
   `vhc_id` pairs of interest.
3. Open **Compare Stat with Session** and upload all three files. Leave *Show only diffs*
   ticked.
4. If mismatches appear, use the `op_id` / `vhc_id` pills to isolate one vehicle and read
   its rows in timestamp order.
5. Check **Compare Stat Outside Session** for events that should not exist at all.
6. Fall back to **Compare Stat Only** if you suspect the session windows themselves are
   wrong — it removes sessions from the equation entirely.

## Tips and limits

- **Uploads are per page.** Switching pages clears the files; re-upload them on the new
  page.
- **Nothing is written to disk.** Uploads live in memory for the session only. Use the
  table's download button to keep a result.
- **Large results render slowly.** Every row is styled individually, so a table with
  hundreds of thousands of cells takes a while. Keep *Show only diffs* on, or narrow with
  the ID pills.
- **A wall of `feeder_only` / `stat_only` rows** usually means a timestamp problem — a
  clock offset between services, or a column parsed as empty — not thousands of genuinely
  missing events. Check a few raw rows in the CSV before treating it as data loss.
- **Missing required column** raises a `KeyError` in the app. Confirm the export includes
  the columns listed above under Input files.
