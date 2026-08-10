from datetime import date

import streamlit as st

import common

st.title("Generate SQL")

c1, c2 = st.columns(2)
with c1:
    op_id = st.number_input("op_id", min_value=0, value=common.DEFAULT_OP_ID, step=1)
with c2:
    local_date = st.date_input("Date (GMT+7)", value=date.today(), format="YYYY-MM-DD")

start_time = common.format_start_time(local_date)
st.caption(
    f"{local_date} 00:00:00 GMT+7 → **{start_time}** UTC — substituted as `${{start_time}}`"
)

queries = common.build_queries(op_id, local_date)

for label, table, query in queries:
    st.subheader(label)
    st.caption(table)
    st.code(query, language="sql")

script = "\n\n".join(query for _, _, query in queries) + "\n"
st.download_button(
    "Download query.sql",
    data=script,
    file_name=f"query_op{int(op_id)}_{local_date}.sql",
    mime="text/plain",
)
