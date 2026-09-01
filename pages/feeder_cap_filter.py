import pandas as pd
import streamlit as st

import common

st.title("Feeder Cap Filter")

feeder_file = st.file_uploader("Feeder data (feeder_vehicle_stat_cap_log.csv)", type="csv")

if feeder_file:
    df = common.read_csv(feeder_file)
    for col in ("rule_op_id", "op_id", "vhc_id", "net_sys_id", "net_lyr_id", "net_id",
                "nod_sys_id", "nod_lyr_id", "nod_id"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    if "add_at" in df.columns:
        df["add_at"] = common.parse_datetime(df["add_at"])

    common.render_filterable_table(df, "feeder rows", key_prefix="feeder_cap")
else:
    st.info("Upload a feeder_vehicle_stat_cap_log.csv to filter.")
