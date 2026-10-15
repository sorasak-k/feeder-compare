import pandas as pd
import streamlit as st

import common

st.title("Compare Cross-Counting")
st.caption(
    "Reconciles feeder_vehicle_stat_cap_log against vehicle_stat_cap_log reading by reading, "
    "accounting for cross-counted (split) readings at stops shared by two routes — see "
    "doc/feeder_stat_cap_cross_counting_explained.md for the full rules."
)

col1, col2 = st.columns(2)
with col1:
    feeder_file = st.file_uploader("Feeder data (feeder_vehicle_stat_cap_log.csv)", type="csv", key="cross_feeder")
with col2:
    stat_file = st.file_uploader("Stat-cap data (vehicle_stat_cap_log.csv)", type="csv", key="cross_stat")

if feeder_file and stat_file:
    feeder_df = common.load_csv(feeder_file, common.FEEDER_TIME_COL)
    for col in ("net_id", "nod_id"):
        if col in feeder_df.columns:
            feeder_df[col] = pd.to_numeric(feeder_df[col], errors="coerce")
    stat_df = common.load_stat_csv(stat_file)

    result = common.compare_cross_counting(feeder_df, stat_df)
    common.render_cross_counting_comparison(result, len(feeder_df), len(stat_df))
else:
    st.info(
        "Upload a feeder log and a stat-cap log CSV to reconcile readings, including "
        "route A→route B splits."
    )
