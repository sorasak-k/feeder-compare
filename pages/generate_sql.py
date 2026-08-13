from datetime import date, time, timedelta

import streamlit as st

import common

st.title("Generate SQL")

op_id = st.number_input("op_id", min_value=0, value=common.DEFAULT_OP_ID, step=1)

st.caption(f"Time range is entered in **{common.LOCAL_TZ_LABEL}** (GMT+7) and converted to UTC for the queries.")

s1, s2, e1, e2 = st.columns(4)
with s1:
    start_date = st.date_input("Start date", value=date.today(), format="YYYY-MM-DD")
with s2:
    start_clock = st.time_input("Start time", value=time.min, step=timedelta(minutes=1))
with e1:
    end_date = st.date_input("End date", value=date.today() + timedelta(days=1), format="YYYY-MM-DD")
with e2:
    end_clock = st.time_input("End time", value=time.min, step=timedelta(minutes=1))

start_utc = common.combine_local(start_date, start_clock)
end_utc = common.combine_local(end_date, end_clock)

st.caption(
    f"{start_date} {start_clock} GMT+7 → **{common.format_utc(start_utc)}** UTC — `${{start_time}}`  \n"
    f"{end_date} {end_clock} GMT+7 → **{common.format_utc(end_utc)}** UTC — `${{end_time}}` (exclusive)"
)

if end_utc <= start_utc:
    st.error("End must be after start.")
    st.stop()

queries = common.build_queries(op_id, start_utc, end_utc)

for label, table, query in queries:
    st.subheader(label)
    st.caption(table)
    st.code(query, language="sql")

script = "\n\n".join(query for _, _, query in queries) + "\n"
stamp = f"{start_utc:%Y%m%d-%H%M}_{end_utc:%Y%m%d-%H%M}"
st.download_button(
    "Download query.sql",
    data=script,
    file_name=f"query_op{int(op_id)}_{stamp}.sql",
    mime="text/plain",
)
