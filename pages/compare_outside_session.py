import pandas as pd
import streamlit as st

import common

st.title("Compare Stat Outside Session")

c1, c2, c3 = st.columns(3)
with c1:
    session_file = st.file_uploader("Session data (session.csv)", type="csv")
with c2:
    feeder_file = st.file_uploader("Feeder data (feeder_vehicle_stat_cap_log.csv)", type="csv")
with c3:
    stat_file = st.file_uploader("Stat-cap data (vehicle_stat_cap_log.csv)", type="csv")

if session_file and feeder_file and stat_file:
    session_df = common.read_csv(session_file)
    session_df["op_id"] = pd.to_numeric(session_df["op_id"], errors="coerce")
    session_df["vhc_id"] = pd.to_numeric(session_df["vhc_id"], errors="coerce")
    session_df["add_at"] = common.parse_datetime(session_df["add_at"])
    session_df["end_at"] = common.parse_datetime(session_df["end_at"])
    session_df["is_tali"] = common.parse_bool(session_df["is_tali"])

    is_tali_choice = st.selectbox("is_tali", ["All", "True", "False"], index=0)
    if is_tali_choice != "All":
        session_df = session_df[session_df["is_tali"] == (is_tali_choice == "True")]

    feeder_df = common.load_csv(feeder_file, common.FEEDER_TIME_COL)
    stat_df = common.load_stat_csv(stat_file)

    filtered_feeder = common.filter_outside_session_window(feeder_df, common.FEEDER_TIME_COL, session_df)
    filtered_stat = common.filter_outside_session_window(stat_df, common.STAT_SRC_TIME_COL, session_df)

    result = common.compare(filtered_feeder, filtered_stat)
    common.render_comparison(result)
else:
    st.info("Upload session.csv, a feeder log, and a stat-cap log CSV to compare rows outside session windows.")
