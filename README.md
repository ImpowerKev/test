# Kev Ops Streamlit App

Streamlit application for managing Azure DevOps Epics.

## Local Development

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deployment on Streamlit Community Cloud

1. Push this repository to GitHub.
2. On [Streamlit Community Cloud](https://share.streamlit.io), create a new app from the repo.
3. Add the following entries under **Secrets**:
   ```toml
   ORG_URL = "https://cgna-stg.visualstudio.com/"
   PROJECT_NAME = "Foodbuy"
   AZURE_PAT = "<your personal access token>"
   ```
4. Deploy the app. The sidebar will use these secret values by default.

## Requirements

See `requirements.txt` for the list of Python dependencies.
