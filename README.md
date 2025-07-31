# KEV OPS

This repository contains a minimal Streamlit app that shows the number of open Epics from Azure DevOps.

## Running locally

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Provide your Azure DevOps credentials either as environment variables or in
   a `secrets.toml` file for Streamlit. Credentials can be stored at the top
   level or under an `[azure]` section. An example file is provided at
   `.streamlit/secrets.example.toml`:

   ```toml
   # secrets.toml
   organization_url = "https://example.visualstudio.com"
   project = "MyProject"
   pat = "<personal access token>"

   # Or using a section
   [azure]
   organization_url = "https://example.visualstudio.com"
   project = "MyProject"
   pat = "<personal access token>"
   ```

   Environment variables `AZURE_DEVOPS_ORG_URL`, `AZURE_DEVOPS_PROJECT`, and
   `AZURE_DEVOPS_PAT` are also recognised as fallbacks.

3. Launch the app:
   ```bash
   streamlit run app.py
   ```
   The page shows the number of open Epics and includes a **Refresh** button to
   update the count. Credentials are read from `st.secrets` so when deploying to
   Streamlit Community Cloud you should create a `.streamlit/secrets.toml` file
   (based on the provided example) and add your organization URL, project and PAT
   there.

## CLI Usage

You can also use `kevops_explore.py` as a command line tool:

```bash
python kevops_explore.py <organization_url> <project> <pat> [--mine] [--count]
```

* `--mine` fetches tasks assigned to the PAT user.
* `--count` prints only the number of tasks instead of the full JSON output.
* `--area` can be supplied multiple times to filter by area path.

## Deploying to Streamlit Cloud

Push this repository to GitHub and connect it to [Streamlit Cloud](https://streamlit.io/cloud). Streamlit Cloud will automatically install the dependencies listed in `requirements.txt` and run `app.py`.

## Notes

The Azure DevOps API only allows up to 200 work item IDs per request. The
`kevops_explore.get_work_items` function retrieves results in batches so large
queries work without hitting the `VS402337` error.

Azure DevOps limits WIQL queries to 20,000 results. The helper functions
`get_open_tasks` and `get_my_open_tasks` page through the IDs using the
`[System.Id] > last_id` pattern so all matching tasks are returned without using
the `TOP` clause, which can cause parsing errors on some servers.
Both functions accept an optional list of area paths if you wish to filter the
results programmatically.
`get_open_epics` provides similar functionality for Epic work items.
