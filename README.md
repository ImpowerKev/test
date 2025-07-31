# Secrets Viewer

This repository contains a minimal Streamlit app that simply displays the contents of `st.secrets`.

## Running locally

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Provide a `secrets.toml` file in the `.streamlit` directory or set environment variables so that `st.secrets` contains values.
3. Launch the app:
   ```bash
   streamlit run app.py
   ```
   The page will show whatever values are stored in `st.secrets`.
