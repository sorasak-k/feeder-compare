import pandas as pd
import streamlit as st

import common

st.title("Sum Filter")
st.caption("Sum cur, inc, and dec after filtering by vhc, network, node, and session.")


def _load_session(session_file, key_prefix):
    session_df = common.read_csv(session_file)
    session_df["op_id"] = pd.to_numeric(session_df["op_id"], errors="coerce")
    session_df["vhc_id"] = pd.to_numeric(session_df["vhc_id"], errors="coerce")
    session_df["add_at"] = common.parse_datetime(session_df["add_at"])
    session_df["end_at"] = common.parse_datetime(session_df["end_at"])
    session_df["is_tali"] = common.parse_bool(session_df["is_tali"])

    is_tali_choice = st.selectbox("is_tali", ["All", "True", "False"], index=0, key=f"{key_prefix}_is_tali")
    if is_tali_choice != "All":
        session_df = session_df[session_df["is_tali"] == (is_tali_choice == "True")]
    return session_df


tab_stat, tab_feeder = st.tabs(["Stat Cap + Session", "Feeder + Session"])

with tab_stat:
    c1, c2 = st.columns(2)
    with c1:
        session_file = st.file_uploader("Session data (session.csv)", type="csv", key="sum_stat_session")
    with c2:
        stat_file = st.file_uploader("Stat-cap data (vehicle_stat_cap_log.csv)", type="csv", key="sum_stat_stat")

    if session_file and stat_file:
        session_df = _load_session(session_file, "sum_stat")
        stat_df = common.load_stat_csv(stat_file)

        matched = common.filter_by_session_window(
            stat_df, common.STAT_SRC_TIME_COL, session_df, extra_cols=common.SESSION_NETWORK_COLS
        )

        filtered = common.render_filterable_table(
            matched,
            "stat-cap rows",
            id_cols=["op_id", "vhc_id"] + common.SESSION_NETWORK_COLS,
            time_cols=["mod_at", "src_at", "session_add_at", "session_end_at"],
            key_prefix="sum_stat",
        )
        common.render_sum_metrics(filtered, "Stat-cap rows")
    else:
        st.info("Upload session.csv and a stat-cap log CSV to sum within session windows.")

with tab_feeder:
    c1, c2 = st.columns(2)
    with c1:
        session_file = st.file_uploader("Session data (session.csv)", type="csv", key="sum_feeder_session")
    with c2:
        feeder_file = st.file_uploader(
            "Feeder data (feeder_vehicle_stat_cap_log.csv)", type="csv", key="sum_feeder_feeder"
        )

    if session_file and feeder_file:
        session_df = _load_session(session_file, "sum_feeder")
        feeder_df = common.load_csv(feeder_file, common.FEEDER_TIME_COL)

        matched = common.filter_by_session_window(feeder_df, common.FEEDER_TIME_COL, session_df)

        exclude_null_node = st.checkbox(
            "Exclude rows with null node (nod_id)", value=True, key="sum_feeder_exclude_null_node"
        )
        if exclude_null_node and "nod_id" in matched.columns:
            matched = matched[matched["nod_id"].notna()]

        filtered = common.render_filterable_table(
            matched,
            "feeder rows",
            id_cols=[
                "op_id", "vhc_id",
                "net_sys_id", "net_lyr_id", "net_id",
                "nod_sys_id", "nod_lyr_id", "nod_id",
            ],
            time_cols=["add_at", "session_add_at", "session_end_at"],
            key_prefix="sum_feeder",
        )
        common.render_sum_metrics(filtered, "Feeder rows")
    else:
        st.info("Upload session.csv and a feeder log CSV to sum within session windows.")
