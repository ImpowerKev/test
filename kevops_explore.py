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
        sys.stderr.write(f"HTTP error {e.code}: {e.reason}\n")
        sys.stderr.write(e.read().decode() + "\n")
        raise


def wiql_query(org_url: str, project: str, pat: str, query: str) -> dict:
    """Execute a WIQL query and return the results."""
    base = _clean_org_url(org_url)
    proj = parse.quote(project, safe="")
    url = f"{base}/{proj}/_apis/wit/wiql?api-version=7.0"
    payload = json.dumps({"query": query}).encode()
    return api_request("POST", url, pat, data=payload)


def get_work_items(org_url: str, ids: list[int], pat: str) -> list[dict]:
    """Retrieve work item details for a list of IDs."""
    if not ids:
        return []
    id_str = ",".join(map(str, ids))
    base = _clean_org_url(org_url)
    url = f"{base}/_apis/wit/workitems?ids={id_str}&api-version=7.0"
    data = api_request("GET", url, pat)
    return data.get("value", [])


def get_open_tasks(org_url: str, project: str, pat: str) -> list[dict]:
    """Return all open tasks in the given project."""
    query = (
        "SELECT [System.Id] FROM WorkItems "
        "WHERE [System.WorkItemType] = 'Task' "
        "AND [System.State] <> 'Closed'"
    )
    result = wiql_query(org_url, project, pat, query)
    ids = [item["id"] for item in result.get("workItems", [])]
    return get_work_items(org_url, ids, pat)


def get_my_open_tasks(org_url: str, project: str, pat: str) -> list[dict]:
    """Return open tasks assigned to the user associated with the PAT."""
    query = (
        "SELECT [System.Id] FROM WorkItems "
        "WHERE [System.WorkItemType] = 'Task' "
        "AND [System.State] <> 'Closed' "
        "AND [System.AssignedTo] = @Me"
    )
    result = wiql_query(org_url, project, pat, query)
    ids = [item["id"] for item in result.get("workItems", [])]
    return get_work_items(org_url, ids, pat)


def main() -> None:
    parser = argparse.ArgumentParser(description="KevOps exploratory CLI")
    parser.add_argument("organization_url", nargs="?", help="Base organization URL, e.g. https://cgna-stg.visualstudio.com")
    parser.add_argument("project", nargs="?", help="Azure DevOps project name")
    parser.add_argument("pat", nargs="?", help="Personal access token")
    parser.add_argument("--mine", action="store_true", help="Fetch tasks assigned to the PAT user")

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

    print(json.dumps(tasks, indent=2))


if __name__ == "__main__":
    main()
