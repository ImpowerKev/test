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
    area_list = [
        p.strip()
        for p in st.text_input("Area path(s), comma-separated").split(",")
        if p.strip()
    ]
    work_type = st.selectbox("Work item type", ["Tasks", "Epics"])

    if work_type == "Tasks":
        tasks = (
            kevops_explore.get_my_open_tasks(org_url, project, pat, area_list)
            if show_mine
            else kevops_explore.get_open_tasks(org_url, project, pat, area_list)
        )
    else:
        tasks = kevops_explore.get_open_epics(org_url, project, pat, area_list)

    if tasks:
        st.write(f"Found {len(tasks)} {work_type.lower()}.")
        st.json(tasks)
    else:
        st.write(f"No open {work_type.lower()} found.")
