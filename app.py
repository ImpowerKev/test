import streamlit as st
import os

import kevops_explore

st.title("KevOps Explorer")

try:
    org_url = st.secrets.get("organization_url")
    project = st.secrets.get("project")
    pat = st.secrets.get("pat")
    azure_section = st.secrets.get("azure", {})
except Exception:
    org_url = project = pat = None
    azure_section = {}

org_url = org_url or azure_section.get("organization_url") or os.getenv("AZURE_DEVOPS_ORG_URL")
project = project or azure_section.get("project") or os.getenv("AZURE_DEVOPS_PROJECT")
pat = pat or azure_section.get("pat") or os.getenv("AZURE_DEVOPS_PAT")

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
        st.write(f"Found {len(tasks)} tasks.")
        st.json(tasks)
    else:
        st.write("No open tasks found.")
