# Sample Streamlit App

This repository contains a minimal Streamlit app for exploring DevOps in Streamlit Cloud.

## Running locally

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Provide your Azure DevOps credentials either as environment variables or in
   a `secrets.toml` file for Streamlit:

   ```toml
   # secrets.toml
   organization_url = "https://example.visualstudio.com"
   project = "MyProject"
   pat = "<personal access token>"
   ```

3. Launch the app:
   ```bash
   streamlit run app.py
   ```

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
