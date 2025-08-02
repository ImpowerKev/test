#!/usr/bin/env python3
"""
Kev Ops
Streamlit Application for managing Azure DevOps Epics

Core Features:
 - Persistent sidebar for configuration
 - Auto-fetch Epics with key fields (ID, Title, State, AssignedTo, Area Path)
 - Static breakdown chart by Area Path with silver bars and steelblue highlight
 - KPI banner: scope, progress, velocity, aging, breakdown, assignees, sync time (with comma formatting)
 - Hierarchical tree of child work items under each Epic, with Active/Inactive split
 - Display of "Last Updated" date for child work items, sorted newest→oldest
 - Lazy-loaded recursive hierarchy and details per-expander with clickable links
 - Efficient batched API calls and caching
 - Glossary tab with business definitions for KPIs
"""
import streamlit as st
import requests
import pandas as pd
import altair as alt
from requests.auth import HTTPBasicAuth
from dateutil import parser
from collections import deque, defaultdict

# Page configuration
st.set_page_config(
    page_title="Kev Ops",
    page_icon=":compass:",
    layout="wide",
)

# --- SIDEBAR STYLING: light silver background ---
st.markdown(
    """
    <style>
    /* Sidebar background */
    [data-testid="stSidebar"] > div:first-child {
        background-color: #f2f2f2 !important;
    }
    /* Sidebar widget container */
    [data-testid="stSidebar"] .css-1d391kg {
        background-color: #f2f2f2 !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)
# -----------------------------------------------

# App title
st.title("KEV OPS - Compass 🧭")

# Sidebar configuration
st.sidebar.header("Configuration")
# Prefer Streamlit secrets for cloud deployment, fall back to defaults
org_url = st.sidebar.text_input(
    "Organization URL",
    st.secrets.get("ORG_URL", "https://cgna-stg.visualstudio.com/")
).rstrip("/")
project = st.sidebar.text_input(
    "Project Name", st.secrets.get("PROJECT_NAME", "Foodbuy")
)
pat = st.sidebar.text_input(
    "Personal Access Token",
    value=st.secrets.get("AZURE_PAT", ""),
    type="password",
)

# Helper: split list into chunks for batch API calls
def chunk_list(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i+n]

# Fetch Epics (cached)
@st.cache_data(show_spinner=False)
def get_epics(org, proj, token):
    wiql = {"query": (
        "SELECT [System.Id] FROM WorkItems "
        "WHERE [System.TeamProject] = @project "
        "AND [System.WorkItemType] = 'Epic' "
        "AND [System.State] NOT IN ('Closed','Cancelled','Removed')"
    )}
    resp = requests.post(
        f"{org}/{proj}/_apis/wit/wiql?api-version=7.0",
        json=wiql,
        auth=HTTPBasicAuth("", token)
    )
    resp.raise_for_status()
    ids = [str(w["id"]) for w in resp.json().get("workItems", [])]
    if not ids:
        return pd.DataFrame(columns=['Epic ID','Title','State','Assigned To','Area Path'])
    fields = ",".join([
        "System.Id","System.Title","System.State",
        "System.AssignedTo","System.AreaPath"
    ])
    records = []
    for batch in chunk_list(ids, 200):
        url = (
            f"{org}/{proj}/_apis/wit/workitems?"
            f"ids={','.join(batch)}&fields={fields}&api-version=7.0"
        )
        r = requests.get(url, auth=HTTPBasicAuth("", token))
        r.raise_for_status()
        for itm in r.json().get("value", []):
            fld = itm.get("fields", {})
            if fld.get("System.State") == "Removed":
                continue
            records.append({
                "Epic ID": itm["id"],
                "Title": fld.get("System.Title",""),
                "State": fld.get("System.State",""),
                "Assigned To": fld.get("System.AssignedTo",{}).get("displayName","Unassigned"),
                "Area Path": fld.get("System.AreaPath","") or "Unspecified"
            })
    return pd.DataFrame(records)

# Build hierarchy recursively (cached)
@st.cache_data(show_spinner=False)
def build_hierarchy(org, proj, token, root_id):
    children = defaultdict(list)
    seen = {root_id}
    queue = deque([root_id])
    while queue:
        batch_size = min(200, len(queue))
        batch = [str(queue.popleft()) for _ in range(batch_size)]
        url = (
            f"{org}/{proj}/_apis/wit/workitems?"
            f"ids={','.join(batch)}&$expand=relations&api-version=7.0"
        )
        resp = requests.get(url, auth=HTTPBasicAuth("", token))
        resp.raise_for_status()
        for wi in resp.json().get('value', []):
            pid = wi['id']
            for rel in wi.get('relations', []):
                if rel.get('rel') == 'System.LinkTypes.Hierarchy-Forward':
                    try:
                        cid = int(rel['url'].rsplit('/',1)[-1])
                    except (ValueError, AttributeError):
                        continue
                    children[pid].append(cid)
                    if cid not in seen:
                        seen.add(cid)
                        queue.append(cid)
    return children

# Flatten descendants for a root
def flatten(children_map, root_id):
    res, stack = [], children_map.get(root_id, []).copy()
    while stack:
        cid = stack.pop()
        res.append(cid)
        stack.extend(children_map.get(cid, []))
    return res

# Fetch detailed fields including Created and Changed (cached)
@st.cache_data(show_spinner=False)
def fetch_details(org, proj, token, ids):
    if not ids:
        return pd.DataFrame()
    details, fields = [], ",".join([
        "System.Id","System.Title","System.WorkItemType","System.State",
        "System.AssignedTo","System.CreatedDate","System.ChangedDate"
    ])
    for batch in chunk_list([str(i) for i in ids], 200):
        url = (
            f"{org}/{proj}/_apis/wit/workitems?"
            f"ids={','.join(batch)}&fields={fields}&api-version=7.0"
        )
        r = requests.get(url, auth=HTTPBasicAuth("", token)); r.raise_for_status()
        for itm in r.json().get('value', []):
            fld = itm.get('fields', {})
            details.append({
                'ID': itm['id'],
                'Title': fld.get("System.Title",""),
                'Type': fld.get("System.WorkItemType",""),
                'State': fld.get("System.State",""),
                'Assigned To': fld.get("System.AssignedTo",{}).get("displayName","Unassigned"),
                'Created': parser.isoparse(fld.get("System.CreatedDate","")),
                'Last Updated': parser.isoparse(fld.get("System.ChangedDate",""))
            })
    return pd.DataFrame(details).set_index('ID')

# Glossary definitions
GLOSSARY = {
    "Total Items": "Total number of child work-items under selected Epics, regardless of state.",
    "Open Items": "Count of all child work-items not in a final state (Closed, Resolved, or Removed).",
    "Closed Items": "Count of child work-items that have reached a final state (Closed, Resolved, or Removed).",
    "% Complete": "Percentage complete = 100 × (Closed Items / Total Items).",
    "New (7d)": "Count of work-items created in the last 7 days.",
    "Closed (7d)": "Count of work-items closed or removed in the last 7 days.",
    "Avg Cycle (days)": "Average time from creation to closing for items that have closed.",
    "Max Age (days)": "Maximum duration of any item (closed duration or current age if still open).",
    "Avg Age (days)": "Average of durations (closed durations or current age for open items).",
    "Type Breakdown": "Distribution of work-item types (Feature, Story, Task, Bug, etc.) under selected Epics.",
    "Top Assignees": "Top 3 users with the most open child work-items.",
    "Last Sync": "UTC timestamp of the last data fetch from Azure DevOps."
}

FINAL_STATES = {"Closed", "Removed", "Resolved"}

# Main UI with tabs
if org_url and project and pat:
    tab1, tab2 = st.tabs(["Dashboard", "Glossary"])

    with tab1:
        df_epics = get_epics(org_url, project, pat)
        if df_epics.empty:
            st.warning("No open Epics found.")
        else:
            df_all = df_epics.copy()
            areas = df_all['Area Path'].value_counts().index.tolist()
            areas.insert(0, '<All Areas>')
            selected = st.sidebar.selectbox("Area Path", areas)
            df_filtered = df_all if selected == '<All Areas>' else df_all[df_all['Area Path'] == selected]

            # compute descendants and details
            all_ids = set()
            for eid in df_filtered['Epic ID']:
                cmap = build_hierarchy(org_url, project, pat, eid)
                all_ids.update(flatten(cmap, eid))
            df_det = fetch_details(org_url, project, pat, sorted(all_ids))

            # KPIs
            now = pd.Timestamp.utcnow()
            total = len(df_det)
            closed_cnt = df_det['State'].isin(FINAL_STATES).sum()
            open_cnt = total - closed_cnt
            pct = round((closed_cnt / total * 100),1) if total else 0
            window = now - pd.Timedelta(days=7)
            new_cnt = (df_det['Created'] >= window).sum()
            closed_recent = ((df_det['State'].isin(FINAL_STATES)) & (df_det['Last Updated'] >= window)).sum()
            cycle = (df_det['Last Updated'] - df_det['Created']).dt.days
            avg_cycle = round(cycle.mean(),1) if not cycle.empty else 0
            ages = (now - df_det['Created']).dt.days
            max_age = int(ages.max()) if not ages.empty else 0
            avg_age = round(ages.mean(),1) if not ages.empty else 0
            type_break = df_det['Type'].value_counts().to_dict()
            assignees = df_det['Assigned To'].value_counts().head(3).to_dict()
            last_sync = now.strftime('%Y-%m-%d %H:%M UTC')

            # render KPI banner
            cols = st.columns(6)
            cols[0].metric("Total Items", f"{total:,}")
            cols[1].metric("Open Items", f"{open_cnt:,}")
            cols[2].metric("Closed Items", f"{closed_cnt:,}")
            cols[3].metric("% Complete", f"{pct}%")
            cols[4].metric("New (7d)", f"{new_cnt:,}")
            cols[5].metric("Closed (7d)", f"{closed_recent:,}")
            cols2 = st.columns(3)
            cols2[0].metric("Avg Cycle (days)", f"{avg_cycle}")
            cols2[1].metric("Max Age (days)", f"{max_age}")
            cols2[2].metric("Avg Age (days)", f"{avg_age}")
            st.markdown(f"**Type Breakdown:** {', '.join(f'{k}: {v:,}' for k,v in type_break.items())}")
            st.markdown(f"**Top Assignees:** {', '.join(f'{k} ({v:,})' for k,v in assignees.items())}")
            st.markdown(f"**Last Sync:** {last_sync}")

            # breakdown chart
            bc = df_all['Area Path'].value_counts().reset_index()
            bc.columns = ['Area Path','Count']
            chart = alt.Chart(bc).mark_bar().encode(
                x=alt.X('Area Path:N', sort=bc['Area Path'].tolist()),
                y='Count:Q',
                color=alt.condition(
                    alt.datum['Area Path'] == selected, alt.value('steelblue'), alt.value('silver')
                ),
                tooltip=['Area Path','Count']
            )
            st.subheader("Epics by Area")
            st.altair_chart(chart, use_container_width=True)

            # epic hierarchy
            st.subheader("Epic Hierarchy")
            base = org_url.rstrip('/')
            for row in df_filtered.itertuples(index=False):
                eid, title = row[0], row[1]
                with st.expander(f"Epic {eid}: {title}"):
                    cmap = build_hierarchy(org_url, project, pat, eid)
                    desc = flatten(cmap, eid)
                    if not desc:
                        st.write("*No linked items*")
                    else:
                        df_e = fetch_details(org_url, project, pat, desc)
                        df_e = df_e.sort_values('Last Updated', ascending=False)
                        df_e['Link'] = df_e.index.to_series().apply(
                            lambda i: f"[{i}]({base}/{project}/_workitems/edit/{i})"
                        )

                        def render_table(df_section):
                            headers = ["Title","Type","State","Assigned To","Last Updated","ID"]
                            md = "| " + " | ".join(headers) + " |\n"
                            md += "|---" * len(headers) + "|\n"
                            for _, r in df_section.iterrows():
                                last = r["Last Updated"].strftime("%Y-%m-%d %H:%M")
                                link = r["Link"]
                                row = [r["Title"], r["Type"], r["State"], r["Assigned To"], last, link]
                                md += "| " + " | ".join(str(v) for v in row) + " |\n"
                            st.markdown(md, unsafe_allow_html=True)

                        active = df_e[~df_e["State"].isin(FINAL_STATES)]
                        inactive = df_e[df_e["State"].isin(FINAL_STATES)]

                        if not active.empty:
                            st.markdown("**Active Work Items**")
                            render_table(active)
                        else:
                            st.write("*None*")

                        if not inactive.empty:
                            st.markdown("**Inactive Work Items**")
                            render_table(inactive)
                        else:
                            st.write("*None*")

    with tab2:
        st.header("KPI Business Definitions")
        for key, desc in GLOSSARY.items():
            st.markdown(f"**{key}**: {desc}")

else:
    st.info("Configure URL, Project, PAT.")
