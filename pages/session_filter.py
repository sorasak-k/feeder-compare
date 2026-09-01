import pandas as pd
import streamlit as st

import common

st.title("Session Filter")

session_file = st.file_uploader("Session data (session.csv)", type="csv")

if session_file:
    df = common.read_csv(session_file)
    df["op_id"] = pd.to_numeric(df["op_id"], errors="coerce")
    df["vhc_id"] = pd.to_numeric(df["vhc_id"], errors="coerce")
    df["add_at"] = common.parse_datetime(df["add_at"])
    df["end_at"] = common.parse_datetime(df["end_at"])

    common.render_filterable_table(df, "sessions", key_prefix="session")
else:
    st.info("Upload a session.csv to filter.")
