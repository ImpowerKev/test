import streamlit as st

st.title("Secrets Viewer")

st.write("Contents of st.secrets:")
st.code(str(dict(st.secrets)))
