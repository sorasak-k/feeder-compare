import streamlit as st

import common

st.title("Stat Cap Filter")

stat_file = st.file_uploader("Stat-cap data (vehicle_stat_cap_log.csv)", type="csv")

if stat_file:
    df = common.load_stat_csv(stat_file)

    common.render_filterable_table(df, "stat-cap rows", key_prefix="stat_cap")
else:
    st.info("Upload a vehicle_stat_cap_log.csv to filter.")
