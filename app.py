import streamlit as st

import common

st.set_page_config(page_title="Stat Cap Compare", layout="wide")

pg = st.navigation(
    [
        st.Page("pages/compare.py", title="Compare Stat Only"),
        st.Page("pages/compare_with_session.py", title="Compare Stat with Session"),
        st.Page("pages/compare_outside_session.py", title="Compare Stat Outside Session"),
        st.Page("pages/session_filter.py", title="Session Filter"),
        st.Page("pages/generate_sql.py", title="Generate SQL"),
    ]
)
st.sidebar.caption(f"Version {common.APP_VERSION}")
pg.run()
