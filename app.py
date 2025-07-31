import os

import streamlit as st

import kevops_explore


st.title("Open Epic Count")


def _load_creds() -> tuple[str | None, str | None, str | None]:
    """Fetch credentials from st.secrets or environment variables."""
    try:
        org = st.secrets.get("organization_url")
        proj = st.secrets.get("project")
        token = st.secrets.get("pat")
        azure = st.secrets.get("azure", {})
    except Exception:
        org = proj = token = None
        azure = {}

    org = org or azure.get("organization_url") or os.getenv("AZURE_DEVOPS_ORG_URL")
    proj = proj or azure.get("project") or os.getenv("AZURE_DEVOPS_PROJECT")
    token = token or azure.get("pat") or os.getenv("AZURE_DEVOPS_PAT")
    return org, proj, token


org_url, project, pat = _load_creds()

if not all([org_url, project, pat]):
    st.error(
        "Azure DevOps credentials are missing. Set them in secrets.toml or environment variables."
    )
else:
    if "epic_count" not in st.session_state or st.button("Refresh"):
        with st.spinner("Fetching open epics..."):
            epics = kevops_explore.get_open_epics(org_url, project, pat)
            st.session_state["epic_count"] = len(epics)

    st.metric("Open Epics", st.session_state["epic_count"])
