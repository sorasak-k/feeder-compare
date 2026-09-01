import streamlit as st

import common

st.set_page_config(page_title="Stat Cap Compare", layout="wide")

st.logo(
    f"""<svg xmlns="http://www.w3.org/2000/svg" width="260" height="26">
    <style>
        .name {{ fill: #262730; }}
        .version {{ fill: #808495; }}
        @media (prefers-color-scheme: dark) {{
            .name {{ fill: #FAFAFA; }}
            .version {{ fill: #A3A8B8; }}
        }}
    </style>
    <text x="0" y="19" font-family="sans-serif" font-size="18" font-weight="600" class="name">Stat Cap Compare<tspan dx="6" font-size="13" font-weight="400" class="version">v{common.APP_VERSION}</tspan></text>
    </svg>""",
    size="large",
)

pg = st.navigation(
    {
        "Test": [
            st.Page("pages/compare.py", title="Compare Stat Only"),
            st.Page("pages/compare_with_session.py", title="Compare Stat with Session"),
            st.Page("pages/compare_outside_session.py", title="Compare Stat Outside Session"),
            st.Page("pages/generate_sql.py", title="Generate SQL"),
        ],
        "Dev": [
            st.Page("pages/session_filter.py", title="Session Filter"),
            st.Page("pages/stat_cap_filter.py", title="Stat Cap Filter"),
            st.Page("pages/feeder_cap_filter.py", title="Feeder Cap Filter"),
            st.Page("pages/sum_filter.py", title="Sum Filter"),
        ],
    }
)
pg.run()
