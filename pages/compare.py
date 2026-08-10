import streamlit as st
from streamlit.navigation import page

import common

st.title("Compare Stat Only")

col1, col2 = st.columns(2)
with col1:
    feeder_file = st.file_uploader("Feeder data (feeder_vehicle_stat_cap_log.csv)", type="csv")
with col2:
    stat_file = st.file_uploader("Stat-cap data (vehicle_stat_cap_log.csv)", type="csv")

if feeder_file and stat_file:
    feeder_df = common.load_csv(feeder_file, common.FEEDER_TIME_COL)
    stat_df = common.load_stat_csv(stat_file)

    result = common.compare(feeder_df, stat_df)
    common.render_comparison(result)
else:
    st.info("Upload both a feeder log and a stat-cap log CSV to compare.")
