# Feeder stat cap — cross-network passenger counting

Standalone explainer for teams consuming `feeder_vehicle_stat_cap_log`. Self-contained: nothing
here depends on reading the service source.

---

## 1. What it is

`feeder_stat_cap` takes raw passenger-counter readings from a vehicle and attributes each one to a
**stop on a route**. The raw reading knows only *when* and *how many*; the output row also says
*where* on the network it happened.

**Input** — `vehicle_stat_cap_log`, one row per counter reading:

| column | meaning |
|---|---|
| `op_id`, `vhc_id` | the vehicle |
| `src_at` | when the reading was taken on the vehicle |
| `mod_at` | when it arrived in the database |
| `cur` | passengers on board at that moment |
| `inc` | boardings since the previous reading |
| `dec` | alightings since the previous reading |

**Output** — `feeder_vehicle_stat_cap_log`, the same reading plus route position:

| column | meaning |
|---|---|
| `rule_op_id` | the operator this row is reported to |
| `op_id`, `vhc_id` | the vehicle |
| `add_at` | **equal to the source reading's `src_at`** |
| `net_sys_id`, `net_lyr_id`, `net_id`, `net_ver` | which route, which version |
| `seq` | position of the stop along that route |
| `nod_sys_id`, `nod_lyr_id`, `nod_id` | the physical stop |
| `is_out_bound` | `true` = the vehicle was not near a stop, so the position is not meaningful |
| `cur`, `inc`, `dec` | the counts |
| `session_add_at`, `session_end_at` | the run the reading was attributed to |
| `node_passenger_rad`, `lon`, `lat`, `cap_time_flag`, `diff_time_ms`, `max_delay_ms` | diagnostics |

Two things about the output that surprise people, and both matter for any query you write:

**One reading can become several rows — one per operator.** A row is written for every operator
entitled to see that vehicle: its owner, plus any operator authorised to monitor it, and only
those that have a feeder rule configured. `rule_op_id` says which operator a row is for. Always
filter or group by it, or you will count the same reading two or three times. A vehicle with no
feeder rule at all produces **no output rows**.

**One reading can become two rows for the same operator.** That is the cross-counting described
below.

---

## 2. What we did

### The problem

A vehicle finishes a run on route A at A's last stop, waits a few minutes, then starts a run on
route B from that same physical stop. The counter keeps logging throughout.

A reading taken while the vehicle sits there holds two different things at once:

- the people getting **off** just finished their trip on **A** — that alighting belongs to A's
  last stop
- the people getting **on** are starting a trip on **B** — that boarding belongs to B's first stop

Before this change, the whole reading was attributed to whichever run happened to own it. One of
the two halves was therefore always on the wrong route — or, if the reading fell in the gap
between the two runs, it was written with no stop at all (`is_out_bound = true`) even though the
vehicle was parked at a real one.

### What changed

A reading taken at the stop two runs share is now **split into two rows**:

| row | counts | attributed to |
|---|---|---|
| alighting row | `dec` kept, `inc` set to `0` | route A, A's last stop |
| boarding row | `inc` kept, `dec` set to `0` | route B, the first stop B was actually seen at |

Both rows keep the original `add_at`. Both usually carry the **same `nod_id`**, because it is one
physical stop — what differs is the route, the `seq`, and which counter is non-zero. `cur` is
copied onto both rows unchanged.

### When a reading is split

All of the following must hold:

1. The previous run is **known to have reached its last stop** — proven by its GPS trail, not by
   the session simply ending. GPS dropouts end runs mid-route all the time, so a run whose arrival
   was never observed never cross-counts.
2. The two runs are on **related routes**: linked as a corridor pair in configuration, or the same
   route when it is a loop (last stop and first stop are the same physical stop).
3. The gap between them is **no longer than the configured tolerance** — currently **300 seconds**
   in all environments. Exactly 300s still splits; 301s does not. A zero gap splits.
4. The reading sits **at the shared stop** — either tagged to that stop, or, if the positioning
   could not place it, taken before the new run's first GPS fix.

### When it is not split

- the previous run's arrival was never observed
- the two runs are one run torn in half by a GPS dropout (same route, resuming where it stopped)
- the gap is longer than the tolerance, or negative
- the routes are unrelated
- the reading is at some other stop along the route
- the reading is untagged but arrived after the new run was already seen somewhere

In all of those the reading passes through as **one row with both counters intact**, exactly as
before.

### Consequence for your queries

`inc` and `dec` are conserved — splitting moves them, it never creates or destroys them.
**`cur` is not**: it is copied onto both halves, so summing `cur` over split readings double
counts. See the next section.

---

## 3. Comparing the two tables

Both tables are in the **LOG** database. What follows is the reasoning, not queries — how to line
the two sides up and what has to be true once you have.

### Step 1 — identify one reading on each side

A source reading is identified by **operator + vehicle + `src_at`**.

The same reading in the output is **operator + vehicle + `add_at`**, because `add_at` is copied
from `src_at` unchanged. That triple is the match key.

Do not match on `mod_at`. That is when the reading reached the database, not when it was taken,
and the output does not carry it.

### Step 2 — separate the output by operator first

One reading can produce a row for several operators: the vehicle's owner, plus any operator
authorised to monitor that vehicle, and only those with a feeder rule configured. `rule_op_id`
says which operator a row is for.

Treat each `rule_op_id` as an **independent copy of the whole dataset**. Pick one and compare it
against the source. Mixing them multiplies every total by the number of operators involved and
makes nothing reconcile.

If a vehicle has no feeder rule anywhere, it produces no output rows at all. That is correct
behaviour, not data loss.

### Step 3 — read the row count for one reading

Having fixed one operator, look at how many output rows share the same operator, vehicle and
`add_at`:

| rows | meaning |
|---|---|
| **1** | normal. The reading was attributed to one stop on one route. Its `cur`, `inc`, `dec` are the source values unchanged. |
| **2** | the reading was **cross-counted** — one physical reading split across the two runs that met at that stop. |
| **0** | either the reading is too recent to have been processed, or no operator holds a feeder rule for that vehicle. Anything else is a genuine drop. |
| **3 or more** | a fault. Nothing in the design produces three rows for one reading. |

The row count is what identifies a split — not the counter values. A split reading whose source
had `inc = 0` and `dec = 0` produces two rows of zeros, which look nothing like a split until you
count them.

### Step 4 — read a split pair

When there are two rows for one reading, they are the two halves of that reading:

- one is the **alighting half**: it keeps `dec`, and its `inc` is zero
- the other is the **boarding half**: it keeps `inc`, and its `dec` is zero

They differ in route (`net_id`, `net_ver`) and position (`seq`), and usually carry the **same
`nod_id`** — one physical stop that two routes share. `session_add_at` / `session_end_at` tell you
which run each half belongs to: the alighting half belongs to the run that just ended, the
boarding half to the run that just started.

To recover the source reading from a split pair:

- source `inc` = sum of the two rows' `inc` (one of them is zero)
- source `dec` = sum of the two rows' `dec` (one of them is zero)
- source `cur` = the `cur` on **either** row — they are identical. **Do not add them.**

### Step 5 — check what must hold

Within one `rule_op_id`, over the same time window:

| check | expected |
|---|---|
| total `inc`, source vs output | **equal**. Splitting moves boardings between rows, it never creates or destroys them. |
| total `dec`, source vs output | **equal**, for the same reason. |
| `cur` | compared **per reading**, never summed. Every output row for a reading carries the source's `cur`. Summing double counts every split. |
| output rows vs source readings | output ≥ source. The excess is exactly the number of splits. |
| `add_at` | every output row's `add_at` equals some source reading's `src_at`, exactly. |
| readings with no output row | only at the trailing edge of the window. |

`inc` and `dec` are the reliable reconciliation. `cur` is a snapshot, not a flow — it is copied,
so it only makes sense reading by reading.

### Things that look like faults but are not

- **`is_out_bound = true` rows.** The vehicle was not near a stop, so `seq` and `nod_id` are not
  meaningful for that row — but the counts are real and belong in the totals. Only a *rise* in
  their share is a signal, usually of a GPS or configuration problem.
- **Missing recent readings.** The service works to roughly half an hour behind now, deliberately,
  so upstream data can settle. The newest readings are legitimately absent.
- **Null counters in the source.** `cur`, `inc` and `dec` can be null there and are read as zero.
  A comparison that does not treat them the same way will show a difference that is not real.
- **Two rows on the same `nod_id`.** Expected for a split — the two routes meet at one stop.
