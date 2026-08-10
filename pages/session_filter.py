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

    op_ids = sorted(df["op_id"].dropna().unique())
    vhc_ids = sorted(df["vhc_id"].dropna().unique())

    c1, c2 = st.columns(2)
    selected_op_ids = c1.multiselect("op_id", op_ids, default=op_ids)
    selected_vhc_ids = c2.multiselect("vhc_id", vhc_ids, default=vhc_ids)

    add_at_min, add_at_max = df["add_at"].min(), df["add_at"].max()
    end_at_min, end_at_max = df["end_at"].min(), df["end_at"].max()

    add_at_range = st.slider(
        "add_at range",
        min_value=add_at_min.to_pydatetime(),
        max_value=add_at_max.to_pydatetime(),
        value=(add_at_min.to_pydatetime(), add_at_max.to_pydatetime()),
    )
    end_at_range = st.slider(
        "end_at range",
        min_value=end_at_min.to_pydatetime(),
        max_value=end_at_max.to_pydatetime(),
        value=(end_at_min.to_pydatetime(), end_at_max.to_pydatetime()),
    )

    filtered = df[
        df["op_id"].isin(selected_op_ids)
        & df["vhc_id"].isin(selected_vhc_ids)
        & df["add_at"].between(*add_at_range)
        & df["end_at"].between(*end_at_range)
    ]

    st.caption(f"{len(filtered)} of {len(df)} sessions shown")
    st.dataframe(filtered, width="stretch")
else:
    st.info("Upload a session.csv to filter.")
