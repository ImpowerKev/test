import streamlit as st

import kevops_explore

st.title("KevOps Explorer")

org_url = st.secrets.get("organization_url")
project = st.secrets.get("project")
pat = st.secrets.get("pat")

if not all([org_url, project, pat]):
    st.error(
        "Azure DevOps credentials are missing. Set them in secrets.toml or environment variables."
    )
else:
    show_mine = st.checkbox("Only show my tasks")
    if show_mine:
        tasks = kevops_explore.get_my_open_tasks(org_url, project, pat)
    else:
        tasks = kevops_explore.get_open_tasks(org_url, project, pat)

    if tasks:
        st.json(tasks)
    else:
        st.write("No open tasks found.")
