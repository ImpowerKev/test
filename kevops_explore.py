# kevops_explore.py
"""
KevOps Explorer – query Azure DevOps work items safely from Streamlit *or* CLI.

Key features
------------
* Auto‑paginates both WIQL and work‑item‑details calls to dodge:
    • VS402337 (>20 000 IDs per WIQL)
    • 400 Bad Request (>200 IDs per work‑item REST call)
* Optional --mine switch (only items assigned to @Me)
* Optional --count switch (print number of tasks instead of JSON list)
* Optional --area filter to limit results by one or more area paths
* Falls back to env vars or Streamlit secrets when args are omitted
"""

from __future__ import annotations
import argparse
import json
import os
import sys
from base64 import b64encode
from urllib import request, parse, error
from typing import List

# ---------------------------------------------------------------------------#
# 0.  Streamlit is optional – keep CLI functional when Streamlit is absent   #
# ---------------------------------------------------------------------------#
try:                                        # pragma: no cover
    import streamlit as st                 # type: ignore
except Exception:
    st = None                              # noqa: N816  (keep var name for later)

# ---------------------------------------------------------------------------#
# 1.  Service‑agnostic helpers                                               #
# ---------------------------------------------------------------------------#
def _clean_org_url(url: str) -> str:
    """Return the organization URL without a trailing slash."""
    return url.rstrip("/")


def _api_request(method: str, url: str, pat: str, data: bytes | None = None) -> dict:
    """Low‑level helper: do a REST round‑trip with PAT auth and JSON body."""
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Basic " + b64encode(f":{pat}".encode()).decode(),
    }
    req = request.Request(url, data=data, headers=headers, method=method)
    try:
        with request.urlopen(req) as resp:
            return json.loads(resp.read().decode())
    except error.HTTPError as e:                       # noqa: WPS441
        _handle_error(f"HTTP error {e.code}: {e.reason}", e.read())
    except error.URLError as e:                        # network issue
        _handle_error(f"Connection error: {e.reason}", None)
    return {}


def _handle_error(msg: str, body: bytes | None) -> None:
    """Display or log an error depending on environment (Streamlit vs CLI)."""
    if st is not None:
        st.error(msg)
        if body:
            st.code(body.decode())
    else:
        sys.stderr.write(msg + "\n")
        if body:
            sys.stderr.write(body.decode() + "\n")


# ---------------------------------------------------------------------------#
# 2.  WIQL & work‑item retrieval with paging                                 #
# ---------------------------------------------------------------------------#
WIQL_BATCH = 20_000          # Azure DevOps hard ceiling
WI_DETAILS_BATCH = 200       # ditto for work‑item details fetch


def _wiql_query(
    org_url: str,
    project: str,
    pat: str,
    query: str,
    top: int | None = None,
) -> dict:
    """Execute a WIQL query; optionally cap rows via &$top= parameter."""
    base = _clean_org_url(org_url)
    proj = parse.quote(project, safe="")
    url = f"{base}/{proj}/_apis/wit/wiql?api-version=7.0"
    if top:
        url += f"&$top={top}"
    payload = json.dumps({"query": query}).encode()
    return _api_request("POST", url, pat, data=payload)


def _paged_wiql(
    org_url: str,
    project: str,
    pat: str,
    base_predicate: str,
) -> List[int]:
    """Return **all** IDs that satisfy *base_predicate*, in 20 000‑ID slices."""
    last_id: int = 0
    all_ids: list[int] = []
    while True:
        wiql = (
            "SELECT [System.Id] FROM WorkItems "
            f"WHERE {base_predicate} AND [System.Id] > {last_id} "
            "ORDER BY [System.Id]"
        )
        result = _wiql_query(org_url, project, pat, wiql, top=WIQL_BATCH)
        ids = [w["id"] for w in result.get("workItems", [])]
        if not ids:               # no more rows – stop paging
            break
        all_ids.extend(ids)
        last_id = ids[-1]         # advance window
    return all_ids


def _get_work_items(org_url: str, ids: List[int], pat: str) -> List[dict]:
    """Retrieve work‑item documents in ≤200‑ID chunks."""
    if not ids:
        return []
    base = _clean_org_url(org_url)
    items: list[dict] = []
    for i in range(0, len(ids), WI_DETAILS_BATCH):
        chunk = ids[i : i + WI_DETAILS_BATCH]           # noqa: E203
        id_str = ",".join(map(str, chunk))
        url = f"{base}/_apis/wit/workitems?ids={id_str}&api-version=7.0"
        items.extend(_api_request("GET", url, pat).get("value", []))
    return items


# ---------------------------------------------------------------------------#
# 3.  Public API callable from Streamlit or tests                            #
# ---------------------------------------------------------------------------#
def _area_predicate(area_paths: List[str]) -> str:
    """Return a WIQL predicate matching any of the given area paths."""
    parts = [f"[System.AreaPath] UNDER '{path}'" for path in area_paths]
    return '(' + ' OR '.join(parts) + ')'


def get_open_tasks(
    org_url: str,
    project: str,
    pat: str,
    area_paths: List[str] | None = None,
) -> List[dict]:
    predicate = (
        "[System.WorkItemType] = 'Task' AND "
        "[System.State] <> 'Closed'"
    )
    if area_paths:
        predicate += " AND " + _area_predicate(area_paths)
    ids = _paged_wiql(org_url, project, pat, predicate)
    return _get_work_items(org_url, ids, pat)


def get_my_open_tasks(
    org_url: str,
    project: str,
    pat: str,
    area_paths: List[str] | None = None,
) -> List[dict]:
    predicate = (
        "[System.WorkItemType] = 'Task' AND "
        "[System.State] <> 'Closed' AND "
        "[System.AssignedTo] = @Me"
    )
    if area_paths:
        predicate += " AND " + _area_predicate(area_paths)
    ids = _paged_wiql(org_url, project, pat, predicate)
    return _get_work_items(org_url, ids, pat)


# ---------------------------------------------------------------------------#
# 4.  CLI entry‑point                                                        #
# ---------------------------------------------------------------------------#
def _resolve_credentials(args: argparse.Namespace) -> tuple[str, str, str]:
    """Pull creds from CLI args, env vars, or Streamlit secrets (if available)."""
    org_url = args.organization_url or os.getenv("AZURE_DEVOPS_ORG_URL")
    project = args.project or os.getenv("AZURE_DEVOPS_PROJECT")
    pat = args.pat or os.getenv("AZURE_DEVOPS_PAT")
    if st is not None:                              # pragma: no cover
        secrets = getattr(st, "secrets", {})
        try:
            org_url = org_url or secrets.get("organization_url")
            project = project or secrets.get("project")
            pat = pat or secrets.get("pat")
            azure = secrets.get("azure", {})
        except Exception:
            azure = {}
        if isinstance(azure, dict):
            org_url = org_url or azure.get("organization_url")
            project = project or azure.get("project")
            pat = pat or azure.get("pat")

    if not all([org_url, project, pat]):
        raise SystemExit(
            "organization_url, project, and pat must be provided "
            "via arguments, environment variables, or Streamlit secrets."
        )
    return org_url, project, pat


def main() -> None:  # noqa: WPS231,WPS213
    parser = argparse.ArgumentParser(description="KevOps exploratory CLI")
    parser.add_argument("organization_url", nargs="?", help="e.g. https://dev.azure.com/org")
    parser.add_argument("project", nargs="?", help="Azure DevOps project name")
    parser.add_argument("pat", nargs="?", help="Personal Access Token")
    parser.add_argument("--mine", action="store_true", help="Only tasks assigned to @Me")
    parser.add_argument(
        "--count", action="store_true", help="Print task count instead of JSON docs"
    )
    parser.add_argument(
        "--area",
        action="append",
        help="Area path(s) to filter (may be repeated)",
    )

    # Ignore unknown flags so that `streamlit run kevops_explore.py` works
    args, _ = parser.parse_known_args()
    org_url, project, pat = _resolve_credentials(args)

    tasks = (
        get_my_open_tasks(org_url, project, pat, args.area)
        if args.mine
        else get_open_tasks(org_url, project, pat, args.area)
    )

    if args.count:
        print(f"{len(tasks)} tasks")
    else:
        print(json.dumps(tasks, indent=2))


# ---------------------------------------------------------------------------#
if __name__ == "__main__":  # pragma: no cover
    main()
