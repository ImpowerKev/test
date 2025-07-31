import streamlit as st
import os

import kevops_explore

st.title("Open Epic Count")

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
    epics = kevops_explore.get_open_epics(org_url, project, pat)
    st.metric("Open Epics", len(epics))
