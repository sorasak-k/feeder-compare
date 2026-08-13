from datetime import datetime, time, timedelta, timezone
from string import Template

import pandas as pd
import streamlit as st

FEEDER_TIME_COL = "add_at"
STAT_TIME_COL = "mod_at"
STAT_SRC_TIME_COL = "src_at"
KEY_COLS = ["op_id", "vhc_id"]
VALUE_COLS = ["cur", "inc", "dec"]


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


def _match_session_windows(df, time_col, session_df):
    sessions = session_df[KEY_COLS + ["add_at", "end_at"]].rename(
        columns={"add_at": "session_add_at", "end_at": "session_end_at"}
    )
    merged = df.reset_index().merge(sessions, on=KEY_COLS)
    mask = merged[time_col].between(merged["session_add_at"], merged["session_end_at"])
    return merged.loc[mask]


def filter_by_session_window(df, time_col, session_df):
    matched = _match_session_windows(df, time_col, session_df).drop_duplicates(subset="index", keep="first").copy()
    matched["session_op_id"] = matched["op_id"]
    matched["session_vhc_id"] = matched["vhc_id"]

    result = df.loc[df.index.isin(matched["index"])].copy()
    return result.join(matched.set_index("index")[SESSION_COLS])


def filter_outside_session_window(df, time_col, session_df):
    matched = _match_session_windows(df, time_col, session_df)
    inside_idx = set(matched["index"])
    return df.loc[~df.index.isin(inside_idx)].copy()


def compare(feeder_df, stat_df, stat_time_col=STAT_SRC_TIME_COL):
    feeder_df = feeder_df.copy()
    stat_df = stat_df.copy()
    feeder_df["match_time"] = feeder_df[FEEDER_TIME_COL]
    stat_df["match_time"] = stat_df[stat_time_col]

    session_cols = [c for c in SESSION_COLS if c in feeder_df.columns and c in stat_df.columns]

    feeder_cols = KEY_COLS + ["match_time", FEEDER_TIME_COL] + VALUE_COLS + session_cols
    stat_cols = KEY_COLS + ["match_time", stat_time_col] + VALUE_COLS + session_cols

    merged = pd.merge(
        feeder_df[feeder_cols],
        stat_df[stat_cols],
        on=KEY_COLS + ["match_time"],
        how="outer",
        suffixes=("_feeder", "_stat"),
        indicator=True,
    )

    for col in session_cols:
        merged[col] = merged[f"{col}_feeder"].combine_first(merged[f"{col}_stat"])
        merged = merged.drop(columns=[f"{col}_feeder", f"{col}_stat"])

    merged = merged.sort_values(KEY_COLS + ["match_time"])

    def row_status(row):
        if row["_merge"] == "left_only":
            return "feeder_only"
        if row["_merge"] == "right_only":
            return "stat_only"
        for col in VALUE_COLS:
            if row[f"{col}_feeder"] != row[f"{col}_stat"]:
                return "mismatch"
        return "match"

    merged["row_status"] = merged.apply(row_status, axis=1)
    merged = merged.drop(columns=["_merge"])

    display_cols = list(KEY_COLS)
    for col in VALUE_COLS:
        display_cols += [f"{col}_feeder", f"{col}_stat"]
    display_cols += [FEEDER_TIME_COL, stat_time_col, "row_status"] + session_cols

    return merged[display_cols]


def highlight_row(row):
    color = {
        "match": "background-color: #1e4620",
        "mismatch": "background-color: #5c1a1a",
        "feeder_only": "background-color: #4d3b0a",
        "stat_only": "background-color: #4d3b0a",
    }.get(row["row_status"], "")
    return [color] * len(row)


LOCAL_TZ = timezone(timedelta(hours=7))
DEFAULT_OP_ID = 52

QUERY_TEMPLATES = [
    (
        "session.csv",
        "vehicle_session_log",
        """select *
from vehicle_session_log vsl
where vsl.op_id = ${op_id}
  and vsl.add_at > ${start_time}::timestamp - interval '30 days'
  and vsl.add_at < ${start_time}::timestamp + interval '1 day'
  and vsl.end_at >= ${start_time}::timestamp
order by vsl.op_id asc, vsl.vhc_id asc, vsl.add_at asc, vsl.end_at asc;""",
    ),
    (
        "feeder_vehicle_stat_cap_log.csv",
        "feeder_vehicle_stat_cap_log",
        """select *
from feeder_vehicle_stat_cap_log fvscl
where fvscl.rule_op_id = ${op_id}
  and fvscl.add_at >= ${start_time}::timestamp
  and fvscl.add_at < ${start_time}::timestamp + interval '1 day'
order by op_id ASC , vhc_id ASC, add_at ASC;""",
    ),
    (
        "vehicle_stat_cap_log.csv",
        "vehicle_stat_cap_log",
        """select op_id, vhc_id, mod_at, coalesce(src_at, mod_at) as src_at, cur, inc, dec
from vehicle_stat_cap_log vscl
where vscl.op_id = ${op_id}
  and vscl.mod_at >= ${start_time}::timestamp - interval '1 day'
  and vscl.mod_at < ${start_time}::timestamp + interval '2 day'
  and vscl.src_at >= ${start_time}::timestamp
  and vscl.src_at < ${start_time}::timestamp + interval '1 day'
order by op_id ASC , vhc_id ASC, mod_at ASC;""",
    ),
]


def local_date_to_utc(local_date, tz=LOCAL_TZ):
    """Midnight of local_date in tz, expressed as a naive UTC datetime.

    A GMT+7 date of 2026-10-10 starts at 2026-10-09 17:00:00 UTC.
    """
    local_start = datetime.combine(local_date, time.min, tzinfo=tz)
    return local_start.astimezone(timezone.utc).replace(tzinfo=None)


def format_start_time(local_date, tz=LOCAL_TZ):
    return local_date_to_utc(local_date, tz).strftime("%Y-%m-%d %H:%M:%S")


def build_queries(op_id, local_date, tz=LOCAL_TZ):
    """Render the three export queries for one op_id and one local (GMT+7) date."""
    values = {"op_id": int(op_id), "start_time": f"'{format_start_time(local_date, tz)}'"}
    return [
        (label, table, Template(template).substitute(values))
        for label, table, template in QUERY_TEMPLATES
    ]


def render_comparison(result):
    total = len(result)
    matches = (result["row_status"] == "match").sum()
    mismatches = (result["row_status"] == "mismatch").sum()
    unmatched = total - matches - mismatches

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total rows compared", total)
    m2.metric("Matches", matches)
    m3.metric("Mismatches", mismatches)
    m4.metric("Unmatched (no counterpart)", unmatched)

    op_ids = sorted(int(v) for v in result["op_id"].dropna().unique())
    vhc_ids = sorted(int(v) for v in result["vhc_id"].dropna().unique())

    o1, o2 = st.columns(2)
    with o1:
        st.caption("op_id (none = all)")
        selected_op_ids = st.pills(
            "op_id", op_ids, selection_mode="multi", default=[], label_visibility="collapsed"
        )
    with o2:
        st.caption("vhc_id (none = all)")
        selected_vhc_ids = st.pills(
            "vhc_id", vhc_ids, selection_mode="multi", default=[], label_visibility="collapsed"
        )

    f1, f2, f3 = st.columns(3)
    show_only_diff = f1.checkbox("Show only diffs", value=True)
    show_feeder_only = f2.checkbox("Show feeder-only", value=True)
    show_stat_only = f3.checkbox("Show stat-cap-only", value=True)

    display_result = result
    if selected_op_ids:
        display_result = display_result[display_result["op_id"].isin(selected_op_ids)]
    if selected_vhc_ids:
        display_result = display_result[display_result["vhc_id"].isin(selected_vhc_ids)]
    if show_only_diff:
        display_result = display_result[display_result["row_status"] != "match"]
    if not show_feeder_only:
        display_result = display_result[display_result["row_status"] != "feeder_only"]
    if not show_stat_only:
        display_result = display_result[display_result["row_status"] != "stat_only"]

    num_cells = display_result.shape[0] * display_result.shape[1]
    max_elements = pd.get_option("styler.render.max_elements")
    if num_cells > max_elements:
        pd.set_option("styler.render.max_elements", num_cells)

    st.dataframe(
        display_result.style.apply(highlight_row, axis=1),
        width="stretch",
    )
