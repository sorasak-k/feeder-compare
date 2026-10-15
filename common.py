from datetime import datetime, time, timedelta, timezone
from string import Template

import pandas as pd
import streamlit as st

APP_VERSION = "0.0.6"

FEEDER_TIME_COL = "add_at"
STAT_TIME_COL = "mod_at"
STAT_SRC_TIME_COL = "src_at"
KEY_COLS = ["op_id", "vhc_id"]
VALUE_COLS = ["cur", "inc", "dec"]
ID_FILTER_COLS = [
    "op_id", "vhc_id",
    "sys_id", "lyr_id",
    "net_sys_id", "net_lyr_id", "net_id",
    "nod_sys_id", "nod_lyr_id", "nod_id",
]
TIME_FILTER_COLS = ["add_at", "end_at", "mod_at", "src_at"]


def _clean_value(value):
    if isinstance(value, str):
        return value.strip().strip('"').strip()
    return value


def read_csv(uploaded_file):
    df = pd.read_csv(uploaded_file, skipinitialspace=True)
    df.columns = [_clean_value(c) for c in df.columns]
    for col in df.columns:
        if pd.api.types.is_object_dtype(df[col]) or pd.api.types.is_string_dtype(df[col]):
            df[col] = df[col].map(_clean_value)
    return df


def parse_datetime(series):
    return pd.to_datetime(series, format="mixed", errors="coerce")


def parse_bool(series):
    def to_bool(value):
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() == "true"
        return bool(value)

    return series.map(to_bool)


def load_csv(uploaded_file, time_col, fallback_time_col=None):
    df = read_csv(uploaded_file)
    if time_col in df.columns:
        parsed = parse_datetime(df[time_col]).dt.floor("ms")
    elif fallback_time_col and fallback_time_col in df.columns:
        parsed = pd.Series(pd.NaT, index=df.index, dtype="datetime64[ns]")
    else:
        raise KeyError(f"CSV is missing the {time_col!r} column")
    if fallback_time_col and fallback_time_col in df.columns:
        fallback = parse_datetime(df[fallback_time_col]).dt.floor("ms")
        parsed = parsed.fillna(fallback)
    df[time_col] = parsed
    for col in KEY_COLS + VALUE_COLS:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def load_stat_csv(uploaded_file):
    """Load a stat-cap log, matching on coalesce(src_at, mod_at) stored as src_at."""
    return load_csv(uploaded_file, STAT_SRC_TIME_COL, STAT_TIME_COL)


SESSION_COLS = ["session_add_at", "session_end_at", "session_op_id", "session_vhc_id"]
SESSION_NETWORK_COLS = ["sys_id", "lyr_id", "net_id"]


def _match_session_windows(df, time_col, session_df, extra_cols=()):
    session_cols = ["add_at", "end_at"] + [c for c in extra_cols if c in session_df.columns]
    sessions = session_df[KEY_COLS + session_cols].rename(
        columns={"add_at": "session_add_at", "end_at": "session_end_at"}
    )
    merged = df.reset_index().merge(sessions, on=KEY_COLS)
    mask = merged[time_col].between(merged["session_add_at"], merged["session_end_at"])
    return merged.loc[mask]


def filter_by_session_window(df, time_col, session_df, extra_cols=()):
    matched = _match_session_windows(df, time_col, session_df, extra_cols).drop_duplicates(
        subset="index", keep="first"
    ).copy()
    matched["session_op_id"] = matched["op_id"]
    matched["session_vhc_id"] = matched["vhc_id"]

    result = df.loc[df.index.isin(matched["index"])].copy()
    extra_present = [c for c in extra_cols if c in session_df.columns]
    return result.join(matched.set_index("index")[SESSION_COLS + extra_present])


ROUTE_COLS = ["net_id", "net_ver", "seq", "nod_id"]
CROSS_COUNT_STATUSES = [
    "match", "split_match", "mismatch", "split_mismatch", "fault", "feeder_only", "stat_only",
]


def _classify_split_pair(group):
    """Given the two feeder rows for one cross-counted reading, return (alighting_row, boarding_row).

    Per feeder_stat_cap_cross_counting_explained.md: the alighting half keeps `dec` with `inc`
    zeroed, the boarding half keeps `inc` with `dec` zeroed. When both counters are zero (a real
    but rare case the doc calls out), fall back to session timing: the alighting half's own
    reading time sits closer to its session's `session_end_at` (the run that is ending).
    """
    dec_rows = group[(group["dec"] > 0) & (group["inc"] == 0)]
    inc_rows = group[(group["inc"] > 0) & (group["dec"] == 0)]
    if len(dec_rows) == 1 and len(inc_rows) == 1:
        return dec_rows.iloc[0], inc_rows.iloc[0]

    ends_soonest_idx = (group["session_end_at"] - group[FEEDER_TIME_COL]).abs().idxmin()
    alighting = group.loc[ends_soonest_idx]
    boarding = group.loc[[i for i in group.index if i != ends_soonest_idx][0]]
    return alighting, boarding


def summarize_feeder_readings(feeder_df):
    """Collapse feeder_vehicle_stat_cap_log rows to one row per (op_id, vhc_id, add_at) reading,
    reconstructing the source counters and, for cross-counted (split) readings, the route-A ->
    route-B transition. See feeder_stat_cap_cross_counting_explained.md section 3.
    """
    present_route_cols = [c for c in ROUTE_COLS if c in feeder_df.columns]
    has_session_end = "session_end_at" in feeder_df.columns
    if has_session_end and not pd.api.types.is_datetime64_any_dtype(feeder_df["session_end_at"]):
        feeder_df = feeder_df.copy()
        feeder_df["session_end_at"] = parse_datetime(feeder_df["session_end_at"])

    records = []
    for (op_id, vhc_id, add_at), group in feeder_df.groupby(KEY_COLS + [FEEDER_TIME_COL], dropna=False):
        row_count = len(group)
        record = {
            "op_id": op_id,
            "vhc_id": vhc_id,
            FEEDER_TIME_COL: add_at,
            "feeder_row_count": row_count,
            "feeder_cur": group["cur"].iloc[0],
            "feeder_inc": group["inc"].sum(min_count=1),
            "feeder_dec": group["dec"].sum(min_count=1),
        }
        for col in present_route_cols:
            record[f"route_a_{col}"] = pd.NA
            record[f"route_b_{col}"] = pd.NA
        if row_count == 2 and present_route_cols and has_session_end:
            alighting, boarding = _classify_split_pair(group)
            for col in present_route_cols:
                record[f"route_a_{col}"] = alighting[col]
                record[f"route_b_{col}"] = boarding[col]
        records.append(record)

    return pd.DataFrame.from_records(records)


def compare_cross_counting(feeder_df, stat_df, stat_time_col=STAT_SRC_TIME_COL):
    """Reconcile feeder_vehicle_stat_cap_log against vehicle_stat_cap_log reading by reading,
    accounting for cross-counted (split) readings instead of comparing rows 1:1.
    """
    summary = summarize_feeder_readings(feeder_df)
    summary["match_time"] = summary[FEEDER_TIME_COL]

    stat = stat_df.copy()
    stat["match_time"] = stat[stat_time_col]
    stat = stat.rename(columns={"cur": "stat_cur", "inc": "stat_inc", "dec": "stat_dec"})

    merged = pd.merge(
        summary,
        stat[KEY_COLS + ["match_time", stat_time_col, "stat_cur", "stat_inc", "stat_dec"]],
        on=KEY_COLS + ["match_time"],
        how="outer",
        indicator=True,
    )

    for col in ("feeder_cur", "feeder_inc", "feeder_dec", "stat_cur", "stat_inc", "stat_dec"):
        merged[col] = merged[col].fillna(0)

    def row_status(row):
        if row["_merge"] == "left_only":
            return "feeder_only"
        if row["_merge"] == "right_only":
            return "stat_only"
        if row["feeder_row_count"] >= 3:
            return "fault"
        ok = (
            row["feeder_cur"] == row["stat_cur"]
            and row["feeder_inc"] == row["stat_inc"]
            and row["feeder_dec"] == row["stat_dec"]
        )
        if row["feeder_row_count"] == 2:
            return "split_match" if ok else "split_mismatch"
        return "match" if ok else "mismatch"

    merged["row_status"] = merged.apply(row_status, axis=1)
    merged["feeder_row_count"] = merged["feeder_row_count"].fillna(0).astype(int)
    merged = merged.drop(columns=["_merge", "match_time"])
    merged = merged.sort_values(KEY_COLS + [FEEDER_TIME_COL])

    return merged


def route_transition_counts(cross_result):
    """Count how many split readings transitioned from each route A to each route B."""
    if "route_a_net_id" not in cross_result.columns:
        return pd.DataFrame(columns=["route_a_net_id", "route_b_net_id", "count"])

    splits = cross_result.dropna(subset=["route_a_net_id", "route_b_net_id"])
    if splits.empty:
        return pd.DataFrame(columns=["route_a_net_id", "route_b_net_id", "count"])

    cols = [c for c in ("route_a_net_id", "route_a_nod_id", "route_b_net_id", "route_b_nod_id") if c in splits.columns]
    return (
        splits.groupby(cols, dropna=False)
        .size()
        .reset_index(name="count")
        .sort_values("count", ascending=False)
    )


def highlight_cross_row(row):
    color = {
        "match": "background-color: #1e4620",
        "split_match": "background-color: #123a52",
        "mismatch": "background-color: #5c1a1a",
        "split_mismatch": "background-color: #7a2a2a",
        "fault": "background-color: #3d0d0d",
        "feeder_only": "background-color: #4d3b0a",
        "stat_only": "background-color: #4d3b0a",
    }.get(row["row_status"], "")
    return [color] * len(row)


LOCAL_TZ = timezone(timedelta(hours=7))  # Asia/Bangkok — no DST, so a fixed offset is exact
LOCAL_TZ_LABEL = "Asia/Bangkok"
DEFAULT_OP_ID = 52

QUERY_TEMPLATES = [
    (
        "session.csv",
        "vehicle_session_log",
        """select *
from vehicle_session_log vsl
where vsl.op_id = ${op_id}
  and vsl.add_at > ${start_time}::timestamp - interval '30 days'
  and vsl.add_at < ${end_time}::timestamp
  and vsl.end_at >= ${start_time}::timestamp
  and vsl.is_tali is TRUE
order by vsl.op_id asc, vsl.vhc_id asc, vsl.add_at asc, vsl.end_at asc;""",
    ),
    (
        "feeder_vehicle_stat_cap_log.csv",
        "feeder_vehicle_stat_cap_log",
        """select *
from feeder_vehicle_stat_cap_log fvscl
where fvscl.rule_op_id = ${op_id}
  and fvscl.add_at >= ${start_time}::timestamp
  and fvscl.add_at < ${end_time}::timestamp
order by op_id ASC , vhc_id ASC, add_at ASC;""",
    ),
    (
        "vehicle_stat_cap_log.csv",
        "vehicle_stat_cap_log",
        """select op_id, vhc_id, mod_at, coalesce(src_at, mod_at) as src_at, cur, inc, dec
from vehicle_stat_cap_log vscl
where vscl.op_id = ${op_id}
  and ((
           vscl.mod_at >= ${start_time}::timestamp - interval '2 day'
               and vscl.mod_at < ${end_time}::timestamp + interval '2 day'
               and vscl.src_at >= ${start_time}::timestamp
               and vscl.src_at < ${end_time}::timestamp
           )
    OR (
           vscl.mod_at >= ${start_time}::timestamp
               and vscl.mod_at < ${end_time}::timestamp
               and vscl.src_at is null
           ))
order by op_id ASC , vhc_id ASC, mod_at ASC;""",
    ),
]


def local_to_utc(local_dt, tz=LOCAL_TZ):
    """A naive local (Asia/Bangkok) datetime, expressed as a naive UTC datetime.

    2026-10-10 00:00 in GMT+7 is 2026-10-09 17:00:00 UTC.
    """
    return local_dt.replace(tzinfo=tz).astimezone(timezone.utc).replace(tzinfo=None)


def combine_local(local_date, local_time, tz=LOCAL_TZ):
    """Join a date and a time picked in local (Asia/Bangkok) terms into a naive UTC datetime."""
    return local_to_utc(datetime.combine(local_date, local_time or time.min), tz)


def format_utc(utc_dt):
    return utc_dt.strftime("%Y-%m-%d %H:%M:%S")


def build_queries(op_id, start_utc, end_utc, tz=LOCAL_TZ):
    """Render the three export queries for one op_id over a UTC window, end exclusive."""
    values = {
        "op_id": int(op_id),
        "start_time": f"'{format_utc(start_utc)}'",
        "end_time": f"'{format_utc(end_utc)}'",
    }
    return [
        (label, table, Template(template).substitute(values))
        for label, table, template in QUERY_TEMPLATES
    ]


def render_filterable_table(df, label, id_cols=ID_FILTER_COLS, time_cols=TIME_FILTER_COLS, key_prefix=""):
    df = df.copy()
    present_id_cols = [col for col in id_cols if col in df.columns]
    present_time_cols = [col for col in time_cols if col in df.columns]

    mask = pd.Series(True, index=df.index)

    for row_start in range(0, len(present_id_cols), 4):
        row_cols = present_id_cols[row_start:row_start + 4]
        columns = st.columns(len(row_cols))
        for column, col in zip(columns, row_cols):
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
            options = sorted(df[col].dropna().unique())
            selected = column.multiselect(col, options, default=options, key=f"{key_prefix}_{col}")
            if len(selected) < len(options):
                mask &= df[col].isin(selected)

    for col in present_time_cols:
        if not pd.api.types.is_datetime64_any_dtype(df[col]):
            df[col] = parse_datetime(df[col])
        col_min, col_max = df[col].min(), df[col].max()
        if pd.isna(col_min) or pd.isna(col_max) or col_min == col_max:
            continue
        col_range = st.slider(
            f"{col} range",
            min_value=col_min.to_pydatetime(),
            max_value=col_max.to_pydatetime(),
            value=(col_min.to_pydatetime(), col_max.to_pydatetime()),
            key=f"{key_prefix}_{col}",
        )
        mask &= df[col].between(*col_range)

    filtered = df[mask]

    st.caption(f"{len(filtered)} of {len(df)} {label} shown")
    st.dataframe(filtered, width="stretch")
    return filtered


def render_sum_metrics(df, label="rows"):
    m1, m2, m3 = st.columns(3)
    m1.metric(label, len(df))
    m2.metric("Sum inc", int(df["inc"].sum()) if len(df) else 0)
    m3.metric("Sum dec", int(df["dec"].sum()) if len(df) else 0)


def render_cross_counting_comparison(result, feeder_row_count, stat_row_count):
    counts = result["row_status"].value_counts()

    i1, i2, i3 = st.columns(3)
    i1.metric("Feeder rows", feeder_row_count)
    i2.metric("Stat-cap rows", stat_row_count)
    i3.metric("Readings", len(result))

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Match", int(counts.get("match", 0)))
    m2.metric("Split match", int(counts.get("split_match", 0)))
    m3.metric("Mismatch", int(counts.get("mismatch", 0) + counts.get("split_mismatch", 0)))
    m4.metric("Fault (3+ rows)", int(counts.get("fault", 0)))
    m5.metric("Unmatched (no counterpart)", int(counts.get("feeder_only", 0) + counts.get("stat_only", 0)))

    st.subheader("Route A → Route B counter")
    st.caption("Cross-counted (split) readings, grouped by the route pair they transitioned between.")
    st.dataframe(route_transition_counts(result), width="stretch")

    st.subheader("Readings")
    op_ids = sorted(int(v) for v in result["op_id"].dropna().unique())
    vhc_ids = sorted(int(v) for v in result["vhc_id"].dropna().unique())

    o1, o2 = st.columns(2)
    with o1:
        st.caption("op_id (none = all)")
        selected_op_ids = st.pills(
            "op_id", op_ids, selection_mode="multi", default=[], label_visibility="collapsed", key="cross_op_id"
        )
    with o2:
        st.caption("vhc_id (none = all)")
        selected_vhc_ids = st.pills(
            "vhc_id", vhc_ids, selection_mode="multi", default=[], label_visibility="collapsed", key="cross_vhc_id"
        )

    default_statuses = [s for s in CROSS_COUNT_STATUSES if s != "match"]
    selected_statuses = st.multiselect(
        "row_status", CROSS_COUNT_STATUSES, default=default_statuses, key="cross_status"
    )

    display_result = result
    if selected_op_ids:
        display_result = display_result[display_result["op_id"].isin(selected_op_ids)]
    if selected_vhc_ids:
        display_result = display_result[display_result["vhc_id"].isin(selected_vhc_ids)]
    display_result = display_result[display_result["row_status"].isin(selected_statuses)]

    num_cells = display_result.shape[0] * display_result.shape[1]
    max_elements = pd.get_option("styler.render.max_elements")
    if num_cells > max_elements:
        pd.set_option("styler.render.max_elements", num_cells)

    st.dataframe(
        display_result.style.apply(highlight_cross_row, axis=1),
        width="stretch",
    )
