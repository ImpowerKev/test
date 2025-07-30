import os
import sys
import json
import argparse
from base64 import b64encode
from urllib import request, parse, error


def _clean_org_url(url: str) -> str:
    """Return the organization URL without a trailing slash."""
    return url.rstrip("/")

try:
    import streamlit as st  # type: ignore
except Exception:  # pragma: no cover - Streamlit may not be installed for CLI use
    st = None


def api_request(method: str, url: str, pat: str, data: bytes | None = None) -> dict:
    """Make an authenticated request to the Azure DevOps REST API."""
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Basic " + b64encode(f':{pat}'.encode()).decode(),
    }
    req = request.Request(url, data=data, headers=headers, method=method)
    try:
        with request.urlopen(req) as resp:
            return json.loads(resp.read().decode())
    except error.HTTPError as e:
        msg = f"HTTP error {e.code}: {e.reason}"
        body = e.read().decode()
        if st is not None:
            st.error(msg)
            if body:
                st.code(body)
        else:
            sys.stderr.write(msg + "\n")
            if body:
                sys.stderr.write(body + "\n")
        return {}
    except error.URLError as e:
        msg = f"Connection error: {e.reason}"
        if st is not None:
            st.error(msg)
        else:
            sys.stderr.write(msg + "\n")
        return {}


def wiql_query(
    org_url: str,
    project: str,
    pat: str,
    query: str,
    top: int | None = None,
) -> dict:
    """Execute a WIQL query and return the results."""
    base = _clean_org_url(org_url)
    proj = parse.quote(project, safe="")
    url = f"{base}/{proj}/_apis/wit/wiql?api-version=7.0"
    if top:
        url += f"&$top={top}"
    payload = json.dumps({"query": query}).encode()
    return api_request("POST", url, pat, data=payload)


WIQL_BATCH = 20_000  # service-side ceiling for WIQL
MAX_WI_BATCH = 200   # Azure DevOps work item retrieval limit


def _paged_wiql(org_url: str, project: str, pat: str, base_query: str) -> list[int]:
    """Return **all** matching work-item IDs, 20_000 at a time."""
    last_id, all_ids = 0, []
    while True:
        wiql = (
            "SELECT [System.Id] FROM WorkItems "
            f"WHERE {base_query} AND [System.Id] > {last_id} "
            "ORDER BY [System.Id]"
        )
        result = wiql_query(org_url, project, pat, wiql, top=WIQL_BATCH)
        ids = [w['id'] for w in result.get('workItems', [])]
        if not ids:
            break
        all_ids.extend(ids)
        last_id = ids[-1]
    return all_ids


def get_work_items(org_url: str, ids: list[int], pat: str) -> list[dict]:
    """Retrieve work items in 200-ID chunks."""
    if not ids:
        return []

    base = _clean_org_url(org_url)
    items: list[dict] = []

    # The work items API only accepts up to 200 IDs per request. Split the
    # list into chunks to avoid HTTP 400 errors (VS402337).
    for start in range(0, len(ids), MAX_WI_BATCH):
        id_chunk = ",".join(map(str, ids[start : start + MAX_WI_BATCH]))
        url = f"{base}/_apis/wit/workitems?ids={id_chunk}&api-version=7.0"
        data = api_request("GET", url, pat)
        items.extend(data.get("value", []))

    return items


def get_open_tasks(org_url: str, project: str, pat: str) -> list[dict]:
    """Return all open tasks in the given project."""
    base_predicate = (
        "[System.WorkItemType] = 'Task' AND "
        "[System.State] <> 'Closed'"
    )
    ids = _paged_wiql(org_url, project, pat, base_predicate)
    return get_work_items(org_url, ids, pat)


def get_my_open_tasks(org_url: str, project: str, pat: str) -> list[dict]:
    """Return open tasks assigned to the user associated with the PAT."""
    base_predicate = (
        "[System.WorkItemType] = 'Task' AND "
        "[System.State] <> 'Closed' AND "
        "[System.AssignedTo] = @Me"
    )
    ids = _paged_wiql(org_url, project, pat, base_predicate)
    return get_work_items(org_url, ids, pat)


def _query_task_ids(org_url: str, project: str, pat: str, mine: bool = False) -> list[int]:
    """Backward compatible helper to fetch task IDs."""
    base_predicate = "[System.WorkItemType] = 'Task' AND [System.State] <> 'Closed'"
    if mine:
        base_predicate += " AND [System.AssignedTo] = @Me"
    return _paged_wiql(org_url, project, pat, base_predicate)


def main() -> None:
    parser = argparse.ArgumentParser(description="KevOps exploratory CLI")
    parser.add_argument("organization_url", nargs="?", help="Base organization URL, e.g. https://cgna-stg.visualstudio.com")
    parser.add_argument("project", nargs="?", help="Azure DevOps project name")
    parser.add_argument("pat", nargs="?", help="Personal access token")
    parser.add_argument("--mine", action="store_true", help="Fetch tasks assigned to the PAT user")
    parser.add_argument(
        "--count",
        action="store_true",
        help="Only print the number of tasks instead of the JSON output",
    )

    # Ignore unknown args so Streamlit can run this script
    args, _ = parser.parse_known_args()

    # Attempt to fill missing values from environment variables or st.secrets
    org_url = args.organization_url or os.getenv("AZURE_DEVOPS_ORG_URL")
    project = args.project or os.getenv("AZURE_DEVOPS_PROJECT")
    pat = args.pat or os.getenv("AZURE_DEVOPS_PAT")
    if st is not None:
        secrets = getattr(st, "secrets", {})
        org_url = org_url or secrets.get("organization_url")
        project = project or secrets.get("project")
        pat = pat or secrets.get("pat")

    if not org_url or not project or not pat:
        parser.error(
            "organization_url, project, and pat must be provided via arguments, environment variables, or st.secrets"
        )

    if args.mine:
        tasks = get_my_open_tasks(org_url, project, pat)
    else:
        tasks = get_open_tasks(org_url, project, pat)

    if args.count:
        print(f"{len(tasks)} tasks")
    else:
        print(json.dumps(tasks, indent=2))


if __name__ == "__main__":
    main()
